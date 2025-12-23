# SwarmCloneBackend
# Copyright (c) 2025 SwarmClone <github.com/SwarmClone> and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import re
from typing import Any, Callable, Dict, List, Set, Optional, Pattern
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from core.logger import log


@dataclass
class Subscription:
    callback: Callable
    is_async: bool
    module_name: str


class MessageBus:
    """
    Rules:
    1. "*" for matching words of any length (not include dots)
    2. "?" for matching a single character
    3. You can use multiple "*" and "?" in a single topic pattern
    """
    def __init__(self):
        self._exact_subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._pattern_subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._pattern_cache: Dict[str, Pattern] = {}
        self._active_tasks: Set[asyncio.Task] = set()
    
    @staticmethod
    @lru_cache(maxsize=1000)
    def _compile_pattern(pattern: str) -> Pattern:
        """Compile topic pattern to regex (cached using LRU)"""
        # Escape dots, replace wildcards
        regex = (pattern
                .replace(".", r"\.")
                .replace("*", r"[^.]*")
                .replace("?", r"[^.]"))
        return re.compile(f"^{regex}$")
    
    async def subscribe(self, module_name: str, topic: str, callback: Callable) -> None:
        async with self._lock:
            subscription = Subscription(
                callback=callback,
                is_async=asyncio.iscoroutinefunction(callback),
                module_name=module_name
            )
            
            if "*" in topic or "?" in topic:
                self._pattern_subscriptions[topic].append(subscription)
            else:
                self._exact_subscriptions[topic].append(subscription)
        
        log.debug(f"Module '{module_name}' subscribed to topic '{topic}'")
    
    async def unsubscribe(self, module_name: str, topic: str = None) -> int: # type: ignore
        removed_count = 0
        async with self._lock:
            if topic:
                # Unsubscribe from specific topic
                if topic in self._exact_subscriptions:
                    before = len(self._exact_subscriptions[topic])
                    self._exact_subscriptions[topic] = [
                        sub for sub in self._exact_subscriptions[topic]
                        if sub.module_name != module_name
                    ]
                    removed_count += before - len(self._exact_subscriptions[topic])
                
                if topic in self._pattern_subscriptions:
                    before = len(self._pattern_subscriptions[topic])
                    self._pattern_subscriptions[topic] = [
                        sub for sub in self._pattern_subscriptions[topic]
                        if sub.module_name != module_name
                    ]
                    removed_count += before - len(self._pattern_subscriptions[topic])
            else:
                # Unsubscribe from all topics
                for topics_dict in [self._exact_subscriptions, self._pattern_subscriptions]:
                    for topic_key in list(topics_dict.keys()):
                        before = len(topics_dict[topic_key])
                        topics_dict[topic_key] = [
                            sub for sub in topics_dict[topic_key]
                            if sub.module_name != module_name
                        ]
                        removed_count += before - len(topics_dict[topic_key])
                        # Clean up empty lists
                        if not topics_dict[topic_key]:
                            del topics_dict[topic_key]
        
        log.debug(f"Removed {removed_count} subscriptions for module '{module_name}'")
        return removed_count
    
    async def publish(self, topic: str, message: Any, max_concurrent: int = 10) -> List[Any]:
        # Collect all matching subscriptions
        subscriptions = []
        async with self._lock:
            # Exact matches
            if topic in self._exact_subscriptions:
                subscriptions.extend(self._exact_subscriptions[topic])
            
            # Pattern matches
            for pattern, subs in self._pattern_subscriptions.items():
                if self._compile_pattern(pattern).match(topic):
                    subscriptions.extend(subs)
        
        if not subscriptions:
            return []
        
        # Execute callbacks with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def execute_callback(sub: Subscription) -> Optional[Any]:
            async with semaphore:
                try:
                    if sub.is_async:
                        result = await sub.callback(message)
                    else:
                        # Run sync callbacks in thread pool
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(None, sub.callback, message)
                    return result
                except Exception as e:
                    log.error(
                        f"Error in callback from module '{sub.module_name}' "
                        f"for topic '{topic}': {e}",
                        exc_info=True
                    )
                    return None
        
        # Execute all callbacks
        tasks = []
        for sub in subscriptions:
            task = asyncio.create_task(execute_callback(sub))
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.remove)
            tasks.append(task)
        
        # Wait for all callbacks to complete
        callback_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and None values
        for result in callback_results:
            if not isinstance(result, Exception) and result is not None:
                results.append(result)
        
        return results
    
    async def cleanup(self) -> None:
        """Cancel all active tasks"""
        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()