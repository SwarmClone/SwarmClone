// sidebar.js
document.addEventListener('DOMContentLoaded', function() {
    // 加载侧边栏
    fetch('../components/sidebar.html')
        .then(response => response.text())
        .then(html => {
            document.querySelector('.nav_bar').innerHTML = html;
            setActiveNavItem();
        });

    // 设置活动状态
    function setActiveNavItem() {
        const pathMap = {
            '/pages/index.html': 'nav-home',
            '/pages/op1.html': 'nav-op1',
            '/pages/opt2.html': 'nav-op2',
            '/pages/opt3.html': 'nav-op3',
            '/pages/opt4.html': 'nav-op4',
            '/pages/live1.html': 'nav-live1',
            '/pages/live2.html': 'nav-live2',
            '/pages/live3.html': 'nav-live3',
            '/pages/live4.html': 'nav-live4',
            '/pages/set-llm.html': 'nav-set-llm',
            '/pages/set-asr.html': 'nav-set-asr',
            '/pages/set-tts.html': 'nav-set-tts',
            '/pages/set-unity.html': 'nav-set-unity',
            '/pages/set-obs.html': 'nav-set-obs',
            '/pages/ab_project.html': 'nav-about-project',
            '/pages/ab_credits.html': 'nav-about-credits',
        };

        // 获取当前路径
        const currentPath = window.location.pathname;
        
        // 清除所有active状态
        document.querySelectorAll('.nav_bar .item').forEach(item => {
            item.classList.remove('active');
        });

        // 设置当前active
        const activeId = pathMap[currentPath];
        if (activeId) {
            const activeElement = document.getElementById(activeId);
            if (activeElement) {
                activeElement.classList.add('active');
            }
        }
    }
});