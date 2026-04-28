<script setup lang="ts">
const ipcHandle = (): void => window.electron.ipcRenderer.send('ping')
</script>

<template>
  <h1 class="creator">Powered by electron-vite</h1>
  <br>
  <div align="center">
    <h3>
      Build an Electron app with
      Vue
      and
      TypeScript
    </h3>
    <p class="tip">Please try pressing <code>F12</code> to open the devTool</p>
    <button @click="ipcHandle">Send IPC</button>
  </div>
</template>
