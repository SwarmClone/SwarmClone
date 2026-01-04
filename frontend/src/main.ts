import PrimeVue from 'primevue/config';
import Aura from '@primeuix/themes/aura';
import {createApp} from "vue";
import App from "./App.vue";

const app = createApp(App);

app.use(PrimeVue, {
    theme: {
        preset: Aura,
        ripple: true,
        options: {
            darkModeSelector: 'system',
        }
    }
 });

app.mount('#app');