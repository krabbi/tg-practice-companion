import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', redirect: 'practices' },
        {
          path: 'practices',
          component: () => import('@/views/PracticesView.vue'),
        },
        {
          path: 'media',
          component: () => import('@/views/MediaView.vue'),
        },
        {
          path: 'journal',
          component: () => import('@/views/JournalView.vue'),
        },
        {
          path: 'reports',
          component: () => import('@/views/ReportsView.vue'),
        },
        {
          path: 'wants',
          component: () => import('@/views/WantsView.vue'),
        },
        {
          path: 'blessings',
          component: () => import('@/views/BlessingsView.vue'),
        },
      ],
    },
  ],
})

export default router
