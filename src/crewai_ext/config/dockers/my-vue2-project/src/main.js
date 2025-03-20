// src/main.js
import Vue from 'vue';
import App from './App.vue';
import router from './router';
import store from './store';
import service from './api/index'; // 引入 Axios 实例

Vue.config.productionTip = false;

// 将 Axios 实例挂载到 Vue 原型上，方便全局使用
Vue.prototype.$http = service;
//全局中使用方法：this.$http.get() / this.$http.post()

new Vue({
  router,
  store,
  render: h => h(App)
}).$mount('#app');