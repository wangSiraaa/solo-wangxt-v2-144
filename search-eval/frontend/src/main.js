import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import ExperimentsView from './views/ExperimentsView.vue'
import ExperimentDetailView from './views/ExperimentDetailView.vue'
import QueryDrilldownView from './views/QueryDrilldownView.vue'
import JudgmentsView from './views/JudgmentsView.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/experiments' },
    { path: '/experiments', component: ExperimentsView },
    { path: '/experiments/:id', component: ExperimentDetailView, props: true },
    {
      path: '/experiments/:id/queries/:qid',
      component: QueryDrilldownView,
      props: true,
    },
    { path: '/judgments', component: JudgmentsView },
  ],
})

createApp(App).use(router).mount('#app')
