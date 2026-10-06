<template>
  <div>
    <nav class="topnav">
      <span class="brand">搜索相关性评测</span>
      <RouterLink to="/experiments">实验</RouterLink>
      <RouterLink to="/judgments">判断集</RouterLink>
    </nav>
    <main class="container">
      <RouterView />
    </main>
  </div>
</template>
