import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "../locales/en/common.json";
import enChat from "../locales/en/chat.json";
import enSidebar from "../locales/en/sidebar.json";
import enLanding from "../locales/en/landing.json";

import esCommon from "../locales/es/common.json";
import esChat from "../locales/es/chat.json";
import esSidebar from "../locales/es/sidebar.json";
import esLanding from "../locales/es/landing.json";

i18n.use(initReactI18next).init({
  resources: {
    en: { common: enCommon, chat: enChat, sidebar: enSidebar, landing: enLanding },
    es: { common: esCommon, chat: esChat, sidebar: esSidebar, landing: esLanding },
  },
  lng: localStorage.getItem("urbanlayer-language") || "en",
  fallbackLng: "en",
  defaultNS: "common",
  interpolation: { escapeValue: false },
});

export default i18n;
