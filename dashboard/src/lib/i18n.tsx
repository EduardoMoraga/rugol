"use client";

/**
 * Sistema i18n minimalista (Capa 15).
 *
 * Por qué no usamos next-intl pleno:
 *   - next-intl pide reestructurar el routing con segments [locale],
 *     mover layouts, configurar middleware. Para una app mono-locale
 *     que solo necesita ES/EN togglable es overkill.
 *   - Aquí hacemos: diccionario en memoria + Context + localStorage.
 *     Una sola fuente de verdad, hot-swap instantáneo, persistente.
 *
 * Uso en componentes:
 *   const { t, locale, setLocale } = useI18n();
 *   return <h1>{t("projects.title")}</h1>;
 *
 * Si una key falta para el locale activo, el hook devuelve la key
 * literal para que la falta sea visible en pantalla y no rompa nada.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Locale = "es" | "en";

const STORAGE_KEY = "rogologo.locale";

type Dict = Record<string, string>;

// Spanish (LATAM neutro, NO rioplatense — el dueño es chileno).
const ES: Dict = {
  // ---- Nav ----
  "nav.projects": "Proyectos",
  "nav.architect": "Architect",
  "nav.configAssistant": "Asistente config",
  "nav.agents": "Agentes",
  "nav.skills": "Skills",
  "nav.schedules": "Schedules",
  "nav.operations": "Operations",
  "nav.antFarm": "Hormiguero",
  "nav.ontology": "Ontología",
  "nav.improvements": "Mejoras",
  "nav.settings": "Settings",

  // ---- Projects home ----
  "projects.title": "Proyectos",
  "projects.description":
    "Cada proyecto es un departamento con misión propia y un equipo de agentes que trabaja en él. Tú eres el CEO; ellos ejecutan.",
  "projects.designWithArchitect": "Diseñar con Architect",
  "projects.newProject": "Nuevo proyecto",
  "projects.activeStat": "Proyectos activos",
  "projects.agentsStat": "Agentes en plantilla",
  "projects.runs24h": "Runs · 24h",
  "projects.cost24h": "Costo · 24h",
  "projects.yourProjects": "Tus proyectos",
  "projects.loading": "Cargando proyectos…",
  "projects.empty": "Todavía no tienes proyectos",
  "projects.emptyDescription":
    "Empieza describiendo una idea — Architect propone el equipo, las skills y los rituales — o crea un proyecto manualmente.",

  // ---- Onboarding hero ----
  "onboarding.tag": "TeamAgent · Increxa",
  "onboarding.headline": "Cada cliente, un departamento de agentes.",
  "onboarding.headlineHighlight": "Tú diriges la estrategia; ellos ejecutan el flujo.",
  "onboarding.pitch":
    "TeamAgent es la sala de control de agentes IA de Increxa. No piensas \"qué agente creo\" — piensas \"qué departamento necesita el cliente\": Market Qualification, Inteligencia Competitiva, Cuenta Cliente, Reporting. El equipo de agentes se arma alrededor del objetivo de negocio.",
  "onboarding.question": "¿Desde dónde te gustaría empezar?",
  "onboarding.seeTemplates": "Ver departamentos disponibles",
  "onboarding.orArchitect": "o descríbelo en una línea con Architect →",
  "onboarding.localFirst": "On-premise.",
  "onboarding.localFirstDesc": "Todo corre en infraestructura controlada. Los datos del cliente no salen.",
  "onboarding.mission": "Misión por departamento.",
  "onboarding.missionDesc": "Cada equipo lee su objetivo de negocio antes de cada tarea.",
  "onboarding.lessons": "Aprendizaje continuo.",
  "onboarding.lessonsDesc": "Lo que el equipo aprende del cliente queda anclado en la ontología.",
  "onboarding.advocate": "Validación cruzada.",
  "onboarding.advocateDesc": "Para las decisiones que importan, una segunda perspectiva con modelo de mayor capacidad.",

  // ---- Template catalog ----
  "templates.title": "Empezar desde un departamento pre-armado",
  "templates.description":
    "Departamentos listos para clonar y adaptar al cliente — Market Qualification, Inteligencia Competitiva, Cuenta Cliente, Reporting Automatizado. Selecciona, ajusta los agentes al ICP del cliente y despliega.",
  "templates.audienceCasual": "Operación interna",
  "templates.audiencePro": "Cliente B2B",
  "templates.agents": "agentes",
  "templates.agent": "agente",
  "templates.schedules": "schedules",
  "templates.schedule": "schedule",
  "templates.see": "Ver",

  // ---- New project dialog ----
  "newProject.title": "Nuevo proyecto",
  "newProject.description":
    "Define una misión clara — los agentes la van a leer antes de cada run para mantenerse anclados.",
  "newProject.name": "Nombre",
  "newProject.namePlaceholder": "Market Qualification — Retail Tech",
  "newProject.shortDescription": "Descripción corta",
  "newProject.shortDescriptionHint": "una sola línea para la tarjeta",
  "newProject.shortDescriptionPlaceholder": "Departamento de calificación de leads para retail de tecnología.",
  "newProject.mission": "Misión",
  "newProject.missionHint": "el objetivo de negocio que el equipo lee antes de cada tarea",
  "newProject.missionPlaceholder":
    "Calificar 50 cuentas semanales en el segmento retail tech LATAM, entregando al equipo comercial leads con BANT validado, dolor verificado y ángulo de conversación específico.",
  "newProject.icon": "Ícono",
  "newProject.color": "Color",
  "newProject.colorChosen": "elegido",
  "newProject.cancel": "Cancelar",
  "newProject.create": "Crear proyecto",
  "newProject.creating": "Creando…",

  // ---- Agent card ----
  "agentCard.lastRun": "último run",
  "agentCard.neverRun": "sin runs",
  "agentCard.open": "Abrir",

  // ---- Agent chat ----
  "chat.title": "Chat con",
  "chat.session": "sesión",
  "chat.busy": "ocupado en otra fuente",
  "chat.cancel": "Cancelar",
  "chat.restart": "Reiniciar",
  "chat.empty": "Empieza la conversación con",
  "chat.knownContext": "Lo que el agente sabe antes de cada respuesta",
  "chat.mission": "Misión",
  "chat.lessons": "lecciones vivas del proyecto que el agente lee antes de responder.",
  "chat.lesson": "lección viva del proyecto que el agente lee antes de responder.",
  "chat.eachTurn":
    "Cada turno se ejecuta como un run real — verás tokens, costo y podrás abrir cualquier respuesta en su página de detalle.",
  "chat.fast": "Heurística",
  "chat.fastHint": "respuesta rápida (haiku)",
  "chat.think": "Pensar",
  "chat.thinkHint": "modelo del agente",
  "chat.deep": "Deliberar",
  "chat.deepHint": "razonamiento profundo (opus)",
  "chat.devilsAdvocate": "Pedir abogado del diablo",
  "chat.devilsAdvocateHint":
    "Después de la respuesta, dispara un segundo run con Opus que la cuestiona.",
  "chat.placeholderBusy": "El agente está respondiendo… espera a que termine",
  "chat.placeholder": "Pídele algo a",
  "chat.placeholderHint": "(Ctrl+Enter para enviar)",
  "chat.sessionContinues":
    "Cada mensaje continúa la sesión — el agente recuerda. Reinicia para empezar de cero.",
  "chat.firstMessage": "El primer mensaje crea una sesión nueva.",
  "chat.you": "tú",
  "chat.agent": "agente",
  "chat.advocate": "abogado del diablo (opus)",
  "chat.streaming": "streaming",
  "chat.queued": "queued",
  "chat.ok": "ok",
  "chat.failed": "failed",
  "chat.cancelled": "cancelled",
  "chat.waiting": "esperando…",

  // ---- Operations dashboard ----
  "operations.title": "Operations",
  "operations.description":
    "Estado en vivo de todos los agentes registrados. Coloca un .md en tu carpeta de agentes, pega un token de Telegram, y ya estás operando.",
  "operations.newAgent": "Nuevo agente",
  "operations.settings": "Settings",
  "operations.statAgents": "Agentes",
  "operations.statRuns24h": "Runs · 24h",
  "operations.statTokens24h": "Tokens · 24h",
  "operations.statCost24h": "Costo · 24h",
  "operations.liveRuns": "Runs en vivo",
  "operations.allAgents": "Todos los agentes →",
  "operations.nothingRunning": "Nada corriendo ahora mismo",
  "operations.nothingRunningHint":
    "Click en Run en cualquier agente o espera a que un schedule dispare.",
  "operations.agentsHeader": "Agentes",
  "operations.manage": "Gestionar →",
  "operations.allIdle": "todos en idle",
  "operations.running": "corriendo",

  // ---- Settings ----
  "settings.title": "Settings",
  "settings.description":
    "Configura tokens y rutas desde acá. Los cambios reinician en caliente los adapters y el watcher — sin tocar el backend.",
  "settings.refreshStatus": "Refrescar estado",
  "settings.dangerZone": "Zona peligrosa",
  "settings.dangerZoneDescription":
    "Restablecer la instalación a estado fresco — útil cuando vas a montar TeamAgent para un cliente nuevo o quieres empezar limpio. Después del reset hay que reiniciar el backend (uvicorn) para que se recreen las tablas vacías. Los departamentos curados siguen disponibles.",
  "settings.resetButton": "Restablecer instalación",
  "settings.resetting": "Reseteando…",

  // ---- Architect ----
  "architect.title": "Architect",
  "architect.description":
    "Describe el objetivo del cliente. TeamAgent propone un departamento de agentes, las skills que comparten, los schedules que los disparan y las semillas de ontología que los conectan. Revisa cada pieza, edita al ICP del cliente, y despliega.",
  "architect.startOver": "Empezar de nuevo",
  "architect.idea": "Tu idea",
  "architect.ideaHint": "una o dos oraciones en lenguaje cotidiano",
  "architect.constraints": "Restricciones",
  "architect.constraintsHint": "opcional · cadencia, canales, qué NO incluir",
  "architect.propose": "Proponer arquitectura",
  "architect.designing": "Diseñando…",
  "architect.deploy": "Deployar",

  // ---- Common ----
  "common.loading": "Cargando…",
  "common.error": "Error",
  "common.save": "Guardar",
  "common.delete": "Borrar",
};

const EN: Dict = {
  // ---- Nav ----
  "nav.projects": "Projects",
  "nav.architect": "Architect",
  "nav.configAssistant": "Config assistant",
  "nav.agents": "Agents",
  "nav.skills": "Skills",
  "nav.schedules": "Schedules",
  "nav.operations": "Operations",
  "nav.antFarm": "Ant farm",
  "nav.ontology": "Ontology",
  "nav.improvements": "Improvements",
  "nav.settings": "Settings",

  // ---- Projects home ----
  "projects.title": "Projects",
  "projects.description":
    "Each project is a department with its own mission and a team of agents that work on it. You're the CEO; they execute.",
  "projects.designWithArchitect": "Design with Architect",
  "projects.newProject": "New project",
  "projects.activeStat": "Active projects",
  "projects.agentsStat": "Agents on staff",
  "projects.runs24h": "Runs · 24h",
  "projects.cost24h": "Cost · 24h",
  "projects.yourProjects": "Your projects",
  "projects.loading": "Loading projects…",
  "projects.empty": "You don't have any projects yet",
  "projects.emptyDescription":
    "Start by describing an idea — Architect proposes the team, the skills and the rituals — or create a project manually.",

  // ---- Onboarding hero ----
  "onboarding.tag": "TeamAgent · Increxa",
  "onboarding.headline": "One client, one agent department.",
  "onboarding.headlineHighlight": "You set the strategy; they run the workflow.",
  "onboarding.pitch":
    "TeamAgent is Increxa's AI agent control room. You don't think \"which agent should I create\" — you think \"which department does the client need\": Market Qualification, Competitive Intelligence, Account Management, Reporting. The agent team forms around the business goal.",
  "onboarding.question": "Where would you like to start?",
  "onboarding.seeTemplates": "See the 5 templates",
  "onboarding.orArchitect": "or describe it in one line with Architect →",
  "onboarding.localFirst": "Local-first.",
  "onboarding.localFirstDesc": "Everything runs on your PC. Your data stays.",
  "onboarding.mission": "Mission per project.",
  "onboarding.missionDesc": "Each team reads its why before every task.",
  "onboarding.lessons": "Living lessons.",
  "onboarding.lessonsDesc": "What the team learns becomes a permanent anchor.",
  "onboarding.advocate": "Devil's advocate.",
  "onboarding.advocateDesc": "For the decisions that matter, two perspectives.",

  // ---- Template catalog ----
  "templates.title": "Start from a template",
  "templates.description":
    "Five projects ready to clone — from the mom building games for her daughter to the founder running their pipeline. Click, customize what you want, deploy.",
  "templates.audienceCasual": "Day to day",
  "templates.audiencePro": "Professional",
  "templates.agents": "agents",
  "templates.agent": "agent",
  "templates.schedules": "schedules",
  "templates.schedule": "schedule",
  "templates.see": "View",

  // ---- New project dialog ----
  "newProject.title": "New project",
  "newProject.description":
    "Define a clear mission — agents will read it before every run to stay anchored.",
  "newProject.name": "Name",
  "newProject.namePlaceholder": "Personal brand",
  "newProject.shortDescription": "Short description",
  "newProject.shortDescriptionHint": "one line for the card",
  "newProject.shortDescriptionPlaceholder":
    "Team that takes care of my public voice on LinkedIn and X.",
  "newProject.mission": "Mission",
  "newProject.missionHint": "the why the team reads before every task",
  "newProject.missionPlaceholder":
    "Build honest technical credibility. Ship 3 pieces a week focused on what I learned in production. Never hype.",
  "newProject.icon": "Icon",
  "newProject.color": "Color",
  "newProject.colorChosen": "selected",
  "newProject.cancel": "Cancel",
  "newProject.create": "Create project",
  "newProject.creating": "Creating…",

  // ---- Agent card ----
  "agentCard.lastRun": "last run",
  "agentCard.neverRun": "never run",
  "agentCard.open": "Open",

  // ---- Agent chat ----
  "chat.title": "Chat with",
  "chat.session": "session",
  "chat.busy": "busy on another source",
  "chat.cancel": "Cancel",
  "chat.restart": "Restart",
  "chat.empty": "Start the conversation with",
  "chat.knownContext": "What the agent knows before every reply",
  "chat.mission": "Mission",
  "chat.lessons": "living lessons of the project the agent reads before replying.",
  "chat.lesson": "living lesson of the project the agent reads before replying.",
  "chat.eachTurn":
    "Every turn runs as a real run — you'll see tokens, cost and can open any reply on its detail page.",
  "chat.fast": "Heuristic",
  "chat.fastHint": "fast reply (haiku)",
  "chat.think": "Think",
  "chat.thinkHint": "agent's model",
  "chat.deep": "Deliberate",
  "chat.deepHint": "deep reasoning (opus)",
  "chat.devilsAdvocate": "Request devil's advocate",
  "chat.devilsAdvocateHint":
    "After the reply, fires a second run with Opus that challenges it.",
  "chat.placeholderBusy": "The agent is replying… wait until it finishes",
  "chat.placeholder": "Ask",
  "chat.placeholderHint": "(Ctrl+Enter to send)",
  "chat.sessionContinues":
    "Every message continues the session — the agent remembers. Restart to start fresh.",
  "chat.firstMessage": "The first message creates a new session.",
  "chat.you": "you",
  "chat.agent": "agent",
  "chat.advocate": "devil's advocate (opus)",
  "chat.streaming": "streaming",
  "chat.queued": "queued",
  "chat.ok": "ok",
  "chat.failed": "failed",
  "chat.cancelled": "cancelled",
  "chat.waiting": "waiting…",

  // ---- Operations dashboard ----
  "operations.title": "Operations",
  "operations.description":
    "Live status across every registered agent. Drop a markdown file in your agents folder, paste a Telegram token, and you're operating.",
  "operations.newAgent": "New agent",
  "operations.settings": "Settings",
  "operations.statAgents": "Agents",
  "operations.statRuns24h": "Runs · 24h",
  "operations.statTokens24h": "Tokens · 24h",
  "operations.statCost24h": "Cost · 24h",
  "operations.liveRuns": "Live runs",
  "operations.allAgents": "All agents →",
  "operations.nothingRunning": "Nothing running right now",
  "operations.nothingRunningHint":
    "Click Run on any agent or wait for a schedule to fire.",
  "operations.agentsHeader": "Agents",
  "operations.manage": "Manage →",
  "operations.allIdle": "all idle",
  "operations.running": "running",

  // ---- Settings ----
  "settings.title": "Settings",
  "settings.description":
    "Configure tokens and paths from here. Changes hot-restart the affected adapters and watcher — no backend bounce.",
  "settings.refreshStatus": "Refresh status",
  "settings.dangerZone": "Danger zone",
  "settings.dangerZoneDescription":
    "Reset the install to a fresh state — useful when moving the app to another PC or starting clean. After reset, restart the backend (uvicorn) so empty tables get recreated. Workspace and the 5 curated templates remain available.",
  "settings.resetButton": "Reset install",
  "settings.resetting": "Resetting…",

  // ---- Architect ----
  "architect.title": "Architect",
  "architect.description":
    "Describe the outcome you want. Rogologo proposes a small team of agents, the skills they share, the schedules that drive them, and the ontology seeds that connect them. Review every piece, edit anything you want, and deploy.",
  "architect.startOver": "Start over",
  "architect.idea": "Your idea",
  "architect.ideaHint": "one or two sentences in plain language",
  "architect.constraints": "Constraints",
  "architect.constraintsHint": "optional · cadence, channels, what NOT to include",
  "architect.propose": "Propose architecture",
  "architect.designing": "Designing…",
  "architect.deploy": "Deploy",

  // ---- Common ----
  "common.loading": "Loading…",
  "common.error": "Error",
  "common.save": "Save",
  "common.delete": "Delete",
};

const DICTS: Record<Locale, Dict> = { es: ES, en: EN };

interface Ctx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("es");

  // Read persisted locale on mount (client-only). Default es.
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "es" || stored === "en") setLocaleState(stored);
    } catch {
      // localStorage may be unavailable (SSR or private mode); ignore.
    }
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
      // Update <html lang> so screen readers pick the right pronunciation.
      document.documentElement.lang = l;
    } catch {
      // ignore
    }
  }, []);

  const t = useCallback(
    (key: string) => {
      const dict = DICTS[locale];
      return dict[key] ?? key;
    },
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
