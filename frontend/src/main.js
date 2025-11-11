import { createApp } from "vue";
import App from "./App.vue";
import "./assets/main.css";
import router from "./router";
import api from "./services/api";

const app = createApp(App);

app.config.globalProperties.$api = api;

app.use(router);
app.mount("#app");

