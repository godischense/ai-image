import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    redirect: '/create'
  },
  {
    path: '/create',
    name: 'Create',
    component: () => import('../views/DirectCreateView.vue')
  },
  {
    path: '/edit/:imageId',
    name: 'Edit',
    component: () => import('../views/EditView.vue'),
    props: true
  },
  {
    path: '/edit',
    name: 'EditNoId',
    component: () => import('../views/EditView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue')
  },
  {
    path: '/prepare',
    name: 'Preparation',
    component: () => import('../views/PreparationView.vue')
  },
  {
    path: '/geo',
    name: 'Geo',
    component: () => import('../views/GeoView.vue')
  },
  {
    path: '/copy-management',
    name: 'CopyManagement',
    component: () => import('../views/CopyManagementView.vue')
  },
  {
    path: '/gigapixel',
    name: 'Gigapixel',
    component: () => import('../views/GigapixelView.vue')
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
