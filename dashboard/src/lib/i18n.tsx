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

const STORAGE_KEY = "rugol.locale";

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
  "nav.memoryGraph": "Memoria",
  "nav.antFarm": "Hormiguero",
  "nav.ontology": "Ontología",
  "nav.improvements": "Mejoras",
  "nav.settings": "Settings",
  "nav.pipelineLead": "Prospectos",
  "nav.pipelineCandidate": "Candidatos",
  "nav.interviews": "Entrevistas",
  "nav.home": "Inicio",
  "nav.guide": "Cómo funciona",
  "nav.searches": "Búsquedas",

  // ---- Nav · secciones (HRO / CRM) ----
  "nav.section.recruitment": "Reclutamiento",
  "nav.section.prospecting": "Prospección",
  "nav.section.agentBrain": "Cerebro del agente",
  "nav.section.configuration": "Configuración",

  // ---- Guía "Cómo funciona" ----
  "guide.hro.title": "Cómo funciona Rugol HRO",
  "guide.hro.subtitle":
    "De un candidato que llega a una terna recomendada, sin que muevas un dedo de más.",
  "guide.crm.title": "Cómo funciona Rugol CRM",
  "guide.crm.subtitle":
    "De un perfil ideal a un prospecto calificado listo para que cierres.",
  "guide.rugol.title": "Cómo funciona Rugol",
  "guide.rugol.body":
    "Rugol es tu sala de control de agentes. Describes un resultado en Architect, él propone un equipo de agentes con su misión, sus skills y sus rituales, y tú los operas desde Proyectos y Operations. El equipo hace el trabajo y desafía tu pensamiento; tú te quedas con la decisión.",
  "guide.flowHeading": "El flujo, paso a paso",

  // Pasos HRO
  "guide.hro.s1.title": "Llega el candidato",
  "guide.hro.s1.body": "Desde Pandapé o con tu link de entrevista.",
  "guide.hro.s2.title": "Screening",
  "guide.hro.s2.body": "El agente evalúa el CV contra el perfil de la búsqueda.",
  "guide.hro.s3.title": "Sofía entrevista",
  "guide.hro.s3.body": "Entrevista por voz, con seis competencias evaluadas en escala BARS.",
  "guide.hro.s4.title": "Pipeline automático",
  "guide.hro.s4.body": "La entrevista se puntúa y el candidato entra solo al tablero.",
  "guide.hro.s5.title": "Terna",
  "guide.hro.s5.body": "Se arma el top 3 recomendado para que tú decidas.",

  // Pasos CRM
  "guide.crm.s1.title": "Defines el ICP",
  "guide.crm.s1.body": "Tu perfil de cliente ideal y la propuesta de valor.",
  "guide.crm.s2.title": "Hunter busca",
  "guide.crm.s2.body": "Genera y enriquece leads desde las fuentes conectadas.",
  "guide.crm.s3.title": "Researcher investiga",
  "guide.crm.s3.body": "Reúne contexto de cada prospecto antes del contacto.",
  "guide.crm.s4.title": "Closer escribe",
  "guide.crm.s4.body": "Redacta outreach personalizado y conversa por los canales.",
  "guide.crm.s5.title": "Strategist califica",
  "guide.crm.s5.body": "Puntúa por ICP y BANT, y los prospectos entran al tablero.",

  // Tabla "Dónde se configura cada cosa"
  "guide.config.heading": "Dónde se configura cada cosa",
  "guide.config.thing": "Qué",
  "guide.config.where": "Dónde",
  "guide.config.anthropic.thing": "Cuenta Anthropic",
  "guide.config.anthropic.where": "Onboarding",
  "guide.config.elevenlabs.thing": "ElevenLabs · Sofía",
  "guide.config.elevenlabs.where": "Settings → Entrevistas por voz",
  "guide.config.telegram.thing": "Telegram",
  "guide.config.telegram.where": "Settings → solo el token",
  "guide.config.tools.thing": "Herramientas por agente · MCP",
  "guide.config.tools.where": "Agentes → abrir el agente → Tools / MCP",

  // Caja link de entrevista
  "guide.link.heading": "Link de entrevista",
  "guide.link.body": "Comparte este link para entrevistar a un candidato.",
  "guide.link.copy": "Copiar",
  "guide.link.open": "Abrir",
  "guide.link.copied": "Link copiado",
  "guide.link.copyFailed": "No se pudo copiar",

  // "Dónde ves cada cosa"
  "guide.see.heading": "Dónde ves cada cosa",
  "guide.see.candidates.title": "Candidatos",
  "guide.see.candidates.body": "El tablero kanban de tu pipeline de selección.",
  "guide.see.interviews.title": "Entrevistas",
  "guide.see.interviews.body": "Los informes de Sofía con las competencias BARS.",
  "guide.see.searches.title": "Búsquedas",
  "guide.see.searches.body": "Cada posición a cubrir con su descripción de cargo.",
  "guide.see.agents.title": "Agentes",
  "guide.see.agents.body": "El cerebro del agente: cómo piensa y qué herramientas usa.",
  "guide.see.prospects.title": "Prospectos",
  "guide.see.prospects.body": "El tablero kanban de tu pipeline comercial.",
  "guide.see.projects.title": "Proyectos",
  "guide.see.projects.body": "Cada iniciativa con su misión y su equipo de agentes.",

  // ---- Pipeline (CRM prospectos / HRO candidatos) ----
  "pipeline.titleLead": "Prospectos",
  "pipeline.titleCandidate": "Candidatos",
  "pipeline.descLead":
    "Pipeline comercial en vivo. Tus agentes registran y mueven prospectos por las etapas; tú decides y cierras.",
  "pipeline.descCandidate":
    "Pipeline de selección en vivo. Tus agentes registran y mueven candidatos por las etapas; tú decides la contratación.",
  "pipeline.add": "Agregar",
  "pipeline.addLead": "Agregar prospecto",
  "pipeline.addCandidate": "Agregar candidato",
  "pipeline.loading": "Cargando pipeline…",
  "pipeline.emptyLead":
    "Aún no hay prospectos. Tus agentes los irán registrando aquí a medida que trabajen, o agrégalos manualmente.",
  "pipeline.emptyCandidate":
    "Aún no hay candidatos. Tus agentes los irán registrando aquí a medida que trabajen, o agrégalos manualmente.",
  "pipeline.colEmpty": "Sin items",
  "pipeline.rugolTitle": "Esta vista pertenece a Rugol CRM / HRO",
  "pipeline.rugolBody":
    "El pipeline de dominio vive en las variantes CRM (prospectos) y HRO (candidatos). En Rugol orquestas a tus agentes desde Proyectos y Operations.",
  "pipeline.score": "Score",
  "pipeline.noScore": "sin score",
  "pipeline.source": "Origen",
  "pipeline.manual": "manual",
  "pipeline.details": "Detalle",
  "pipeline.data": "Datos",
  "pipeline.noData": "Sin datos estructurados.",
  "pipeline.history": "Historial",
  "pipeline.noNotes": "Aún no hay notas registradas.",
  "pipeline.addNote": "Agregar nota",
  "pipeline.notePlaceholder": "Escribe una nota…",
  "pipeline.saveNote": "Guardar nota",
  "pipeline.savingNote": "Guardando…",
  "pipeline.delete": "Borrar item",
  "pipeline.deleteConfirm": "¿Borrar este item del pipeline?",
  "pipeline.moveBack": "Etapa anterior",
  "pipeline.moveForward": "Etapa siguiente",
  "pipeline.title": "Título",
  "pipeline.titlePlaceholder": "Nombre del prospecto / candidato",
  "pipeline.subtitle": "Subtítulo",
  "pipeline.subtitlePlaceholder": "Empresa, cargo, detalle corto",
  "pipeline.stage": "Etapa",
  "pipeline.cancel": "Cancelar",
  "pipeline.create": "Crear",
  "pipeline.creating": "Creando…",
  "pipeline.created": "Item creado",
  "pipeline.deleted": "Item borrado",
  "pipeline.noteAdded": "Nota agregada",
  "pipeline.moved": "Item movido",

  // ---- Interviews (Sofía / HRO) ----
  "interviews.title": "Entrevistas",
  "interviews.desc":
    "Informes de entrevista de Sofía. Cada candidato evaluado trae su veredicto, las seis competencias con su puntaje y la evidencia citada.",
  "interviews.loading": "Cargando entrevistas…",
  "interviews.empty":
    "Aún no hay entrevistas. Cuando Sofía entreviste candidatos, sus informes aparecerán aquí.",
  "interviews.notHroTitle": "Esta vista pertenece a Rugol HRO",
  "interviews.notHroBody":
    "Las entrevistas de Sofía solo aplican a la variante de selección de personal (HRO).",
  "interviews.verdict": "Veredicto",
  "interviews.verdict.avanzar": "Avanzar",
  "interviews.verdict.dudoso": "Dudoso",
  "interviews.verdict.descartar": "Descartar",
  "interviews.confidence": "Confianza",
  "interviews.confidence.alta": "alta",
  "interviews.confidence.media": "media",
  "interviews.confidence.baja": "baja",
  "interviews.competencies": "Competencias",
  "interviews.noScore": "s/p",
  "interviews.evidence": "Evidencia",
  "interviews.noEvidence": "Sin evidencia citada.",
  "interviews.risks": "Riesgos",
  "interviews.noRisks": "Sin riesgos señalados.",
  "interviews.history": "Historial",
  "interviews.noNotes": "Aún no hay notas registradas.",
  "interviews.manual": "manual",
  "interviews.expand": "Ver detalle",
  "interviews.collapse": "Ocultar detalle",
  "interviews.count": "entrevistas",

  // ---- Entrevista in-app con Sofía (texto) ----
  "interviews.live.start": "Entrevistar con Sofía",
  "interviews.live.title": "Entrevista con Sofía",
  "interviews.live.intro":
    "Sofía conduce la entrevista aquí mismo: pregunta una cosa a la vez, tú anotas la respuesta del candidato. Al cerrar, la evalúa con BARS y la registra en el pipeline.",
  "interviews.live.candidateName": "Nombre del candidato",
  "interviews.live.candidateNamePlaceholder": "María López",
  "interviews.live.role": "Rol / seniority",
  "interviews.live.rolePlaceholder": "Promotora retail",
  "interviews.live.search": "Búsqueda",
  "interviews.live.searchHint": "Sofía usa la descripción de cargo de esta búsqueda",
  "interviews.live.noSearch": "Sin búsqueda",
  "interviews.live.begin": "Comenzar entrevista",
  "interviews.live.candidatePlaceholder": "Escribe la respuesta del candidato…",
  "interviews.live.send": "Enviar",
  "interviews.live.thinking": "Sofía está pensando…",
  "interviews.live.finish": "Finalizar y evaluar",
  "interviews.live.finishing": "Evaluando…",
  "interviews.live.scored": "Entrevista evaluada y registrada en el pipeline",
  "interviews.live.scoreError": "No se pudo evaluar la entrevista",
  "interviews.live.turnError": "Sofía no pudo responder",
  "interviews.live.needName": "Pon el nombre del candidato primero",
  "interviews.live.you": "Candidato",
  "interviews.live.sofia": "Sofía",
  "interviews.live.minTurns": "Responde al menos un par de preguntas antes de evaluar.",
  "interviews.live.close": "Cerrar",
  "interviews.live.restart": "Reiniciar",

  // ---- Voz Sofía (ElevenLabs) ----
  "voice.sync": "Sincronizar con ElevenLabs",
  "voice.syncing": "Sincronizando…",
  "voice.syncDone": "{n} entrevista(s) nueva(s)",
  "voice.syncNone": "Sin entrevistas nuevas",
  "voice.syncError": "No se pudo sincronizar",
  "voice.notConfigured":
    "Conecta tu cuenta de ElevenLabs en Ajustes para traer las entrevistas de Sofía.",
  "voice.goToSettings": "Ir a Ajustes",
  "voice.launch": "Lanzar entrevista de voz",

  // ---- HRO Cockpit (sala de reclutamiento — inicio) ----
  "hro.cockpit.tag": "Sala de reclutamiento",
  "hro.cockpit.title": "Sala de reclutamiento",
  "hro.cockpit.subtitle":
    "Tus agentes evalúan, Sofía entrevista, y todo se ordena solo en tu pipeline.",
  "hro.cockpit.stat.candidates": "candidatos",
  "hro.cockpit.stat.interviews": "entrevistas hechas",

  // Flujo (5 pasos)
  "hro.cockpit.flow.heading": "Cómo funciona, de punta a punta",
  "hro.cockpit.flow.s1.title": "Llega el candidato",
  "hro.cockpit.flow.s1.body": "Desde Pandapé o con tu link de entrevista.",
  "hro.cockpit.flow.s2.title": "Screening",
  "hro.cockpit.flow.s2.body": "hro-screener filtra y ordena por ajuste al perfil.",
  "hro.cockpit.flow.s3.title": "Sofía entrevista",
  "hro.cockpit.flow.s3.body": "Entrevista por voz, con evaluación BARS.",
  "hro.cockpit.flow.s4.title": "Pipeline automático",
  "hro.cockpit.flow.s4.body": "Cada candidato avanza solo por las etapas.",
  "hro.cockpit.flow.s5.title": "Terna",
  "hro.cockpit.flow.s5.body": "hro-matcher arma la terna final para ti.",

  // Conexiones
  "hro.cockpit.connections.heading": "Qué está conectado",
  "hro.cockpit.connections.active": "activo",
  "hro.cockpit.connections.connected": "conectado",
  "hro.cockpit.connections.missing": "falta configurar",
  "hro.cockpit.connections.notRunning": "configurado · no corre",
  "hro.cockpit.connections.notConnected": "no conectado",
  "hro.cockpit.connections.configure": "Configurar",
  "hro.cockpit.connections.anthropic.name": "Anthropic",
  "hro.cockpit.connections.anthropic.body":
    "El cerebro de tus agentes. Va incluido en tu suscripción.",
  "hro.cockpit.connections.elevenlabs.name": "ElevenLabs · Sofía",
  "hro.cockpit.connections.elevenlabs.body":
    "La voz de Sofía para entrevistar a los candidatos.",
  "hro.cockpit.connections.telegram.name": "Telegram",
  "hro.cockpit.connections.telegram.body":
    "Recibe alertas y opera el pipeline desde tu teléfono.",

  // Link de entrevista
  "hro.cockpit.link.heading": "Link de entrevista",
  "hro.cockpit.link.body": "Comparte este link para entrevistar a un candidato.",
  "hro.cockpit.link.copy": "Copiar",
  "hro.cockpit.link.open": "Abrir",
  "hro.cockpit.link.copied": "Link copiado",
  "hro.cockpit.link.copyFailed": "No se pudo copiar",

  // Acciones rápidas
  "hro.cockpit.actions.heading": "Acciones rápidas",
  "hro.cockpit.actions.candidates.title": "Ver candidatos",
  "hro.cockpit.actions.candidates.body": "Tu pipeline de selección en vivo.",
  "hro.cockpit.actions.interviews.title": "Ver entrevistas",
  "hro.cockpit.actions.interviews.body": "Los informes que dejó Sofía.",
  "hro.cockpit.actions.sync.title": "Sincronizar entrevistas",
  "hro.cockpit.actions.sync.body": "Trae las últimas entrevistas de ElevenLabs.",
  "hro.cockpit.actions.configureSofia.title": "Configurar a Sofía",
  "hro.cockpit.actions.configureSofia.body": "Ajusta a tu entrevistadora de voz.",

  // ---- Copiloto (HRO home) ----
  "hro.copilot.name": "Copiloto",
  "hro.copilot.title": "Tu copiloto de reclutamiento",
  "hro.copilot.subtitle":
    "Pídele en lenguaje natural: abrir una búsqueda, analizar CVs, recomendar candidatos. Él coordina al equipo y te trae resultados — tú decides.",
  "hro.copilot.ex1": "Tengo una vacante de promotor retail en Maipú. ¿Qué necesitas de mí?",
  "hro.copilot.ex2": "Recomiéndame candidatos de mi pipeline para una posición de promotor.",
  "hro.copilot.ex3": "Analiza los CVs de mi última búsqueda y arma el ranking.",
  "hro.copilot.ex4": "¿A quién debería entrevistar primero y por qué?",
  "hro.copilot.unavailable":
    "El copiloto se está preparando. Si no aparece, revisa que el agente 'assistant' exista en Agentes.",

  // ---- Embudo con agentes (qué hace cada uno) ----
  "hro.funnel.heading": "El equipo que coordina tu copiloto",
  "hro.funnel.note":
    "Tú le hablas al copiloto en lenguaje natural; él decide y coordina a este equipo. No es un flujo rígido A→B: se adapta a lo que pides.",
  "hro.funnel.driver": "Lo hace",
  "hro.funnel.s1.title": "Llegan los CVs",
  "hro.funnel.s1.body": "Desde tus fuentes (Pandapé, portales, Drive, carpeta) o el link de entrevista.",
  "hro.funnel.s1.agent": "Conector",
  "hro.funnel.s2.title": "Screening",
  "hro.funnel.s2.body": "Evalúa cada CV contra el perfil y puntúa 1-5 con evidencia.",
  "hro.funnel.s2.agent": "Screener",
  "hro.funnel.s3.title": "Filtro duro",
  "hro.funnel.s3.body": "Aplica los requisitos no negociables (ubicación, disponibilidad).",
  "hro.funnel.s3.agent": "Knockout",
  "hro.funnel.s4.title": "Entrevista",
  "hro.funnel.s4.body": "Sofía entrevista por competencias (BARS) y deja su informe.",
  "hro.funnel.s4.agent": "Sofía",
  "hro.funnel.s5.title": "Terna",
  "hro.funnel.s5.body": "Compara a los entrevistados y arma el top 3 recomendado.",
  "hro.funnel.s5.agent": "Matcher",
  "hro.funnel.s6.title": "Oferta",
  "hro.funnel.s6.body": "Redacta la comunicación al elegido y a los no seleccionados.",
  "hro.funnel.s6.agent": "Oferta",

  // ---- Fuentes de CV ----
  "cvSources.title": "Fuentes de CV",
  "cvSources.subtitle": "De dónde tu copiloto baja candidatos. Agrega las que uses: el agente arma la integración y llena tu pipeline.",
  "cvSources.empty": "Aún no conectas ninguna fuente. Agrega una para que tu copiloto traiga candidatos.",
  "cvSources.add": "Agregar fuente",
  "cvSources.adding": "Agregando…",
  "cvSources.type": "Tipo de fuente",
  "cvSources.name": "Nombre (opcional)",
  "cvSources.namePlaceholder": "Ej: Pandapé — cuenta retail",
  "cvSources.credentials": "Token / credenciales",
  "cvSources.credentialsOptional": "opcional",
  "cvSources.credentialsPlaceholder": "Pega el token o usuario:clave",
  "cvSources.added": "Fuente agregada",
  "cvSources.addError": "No se pudo agregar la fuente",
  "cvSources.remove": "Quitar",
  "cvSources.removed": "Fuente eliminada",
  "cvSources.removeError": "No se pudo eliminar",
  "cvSources.connected": "configurada",
  "cvSources.secure": "Tu token se guarda solo en tu equipo.",

  // ---- Onboarding Instalar → Configurar → Enjoy ----
  "onboarding.wizard.tag": "Bienvenida",
  "onboarding.wizard.title": "Pongamos a andar tu reclutamiento",
  "onboarding.wizard.subtitle": "Tres pasos y listo. Lo puedes cambiar después en Ajustes.",
  "onboarding.wizard.step": "Paso",
  "onboarding.wizard.of": "de",
  "onboarding.wizard.next": "Siguiente",
  "onboarding.wizard.back": "Atrás",
  "onboarding.wizard.skip": "Omitir por ahora",
  "onboarding.wizard.finish": "Empezar",
  "onboarding.wizard.finishing": "Listo…",
  "onboarding.wizard.done": "¡Todo listo! Tu copiloto está activo.",
  // Paso Anthropic
  "onboarding.anthropic.title": "Tu cerebro: Anthropic",
  "onboarding.anthropic.body": "Tu copiloto y los agentes piensan con tu cuenta de Anthropic. Ya viene incluida en esta app — nada que hacer aquí.",
  "onboarding.anthropic.ok": "Conectado por tu suscripción",
  // Paso Telegram
  "onboarding.telegram.title": "Opera desde tu teléfono: Telegram",
  "onboarding.telegram.body": "Pega el token de tu bot de @BotFather y podrás pedirle cosas a tu copiloto desde el celular. Es opcional.",
  // Paso ElevenLabs
  "onboarding.eleven.title": "Entrevistas por voz: Sofía",
  "onboarding.eleven.body": "Conecta tu cuenta de ElevenLabs para que Sofía entreviste por voz. Es opcional: también funciona por texto.",
  "onboarding.eleven.key": "API key de ElevenLabs",
  "onboarding.eleven.agent": "Agent ID",
  // Paso fuentes
  "onboarding.sources.title": "¿De dónde sacamos candidatos?",
  "onboarding.sources.body": "Conecta al menos una fuente de CV (Pandapé, Chiletrabajo, Computrabajo, Drive o una carpeta). Puedes agregar más después.",
  "onboarding.saved": "Configuración guardada",

  // ---- Memory graph ----
  "memgraph.title": "Red de memoria",
  "memgraph.desc":
    "La red neuronal de tus agentes, estilo Obsidian: cada nodo es una memoria o un concepto; las líneas son los [[enlaces]] que ellos mismos tejen al aprender.",
  "memgraph.search": "Buscar memoria o concepto…",
  "memgraph.allAgents": "Todos los agentes",
  "memgraph.agents": "agentes",
  "memgraph.memories": "memorias",
  "memgraph.concepts": "conceptos",
  "memgraph.links": "enlaces",
  "memgraph.kind.agent": "agente",
  "memgraph.kind.user": "usuario",
  "memgraph.kind.feedback": "feedback",
  "memgraph.kind.project": "proyecto",
  "memgraph.kind.reference": "referencia",
  "memgraph.kind.note": "nota",
  "memgraph.kind.concept": "concepto",
  "memgraph.emptyTitle": "Todavía no hay memorias",
  "memgraph.emptyBody":
    "Hablá con un agente (Telegram o chat) y volvé: cada cosa que aprenda aparece aquí como un nodo, y sus conexiones van tejiendo la red.",
  "memgraph.panel.agent": "Agente — el centro de su propio cluster de memorias.",
  "memgraph.panel.concept": "Concepto — un [[enlace]] que todavía no es memoria. Une a quienes lo mencionan.",
  "memgraph.panel.degree": "Conexiones",
  "memgraph.hint":
    "Arrastrá los nodos · rueda para zoom · click en un nodo para leer la memoria · click en vacío para deseleccionar.",

  // ---- Projects home ----
  "projects.title": "Proyectos",
  "projects.description":
    "Cada proyecto reúne un equipo de agentes con una misión propia. Ellos hacen el trabajo y desafían tu pensamiento; tú te quedas con la decisión.",
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

  // ---- Búsquedas (HRO: un proyecto ES una posición a cubrir) ----
  "searches.title": "Búsquedas",
  "searches.description":
    "Cada búsqueda es una posición a cubrir, con su descripción de cargo y su equipo de agentes. Ellos evalúan y entrevistan; tú decides la contratación.",
  "searches.newSearch": "Nueva búsqueda",
  "searches.empty": "Todavía no tienes búsquedas",
  "searches.emptyDescription":
    "Crea una búsqueda para abrir una posición — describe el cargo y deja que tus agentes evalúen a los candidatos.",
  "searches.activeStat": "Búsquedas activas",
  "newSearch.title": "Nueva búsqueda",
  "newSearch.description":
    "Define la posición a cubrir. Tus agentes leen el alcance y la descripción de cargo antes de evaluar a cada candidato.",
  "newSearch.name": "Nombre de la posición",
  "newSearch.namePlaceholder": "Analista de Datos Senior",
  "newSearch.create": "Crear búsqueda",
  "project.jobDescription": "Descripción de cargo",
  "project.jobDescriptionHint": "el perfil que el agente usa para evaluar candidatos",
  "project.jobDescriptionPlaceholder":
    "Responsabilidades, requisitos, competencias clave y todo lo que define el perfil de la posición.",
  "project.scope": "Alcance / objetivo",
  "project.scopeHint": "el porqué que el equipo lee antes de cada tarea",
  "project.noJobDescription": "Sin descripción de cargo todavía.",

  // ---- Fuente de CVs (HRO: carpeta de CVs por búsqueda) ----
  "cvSource.title": "Fuente de CVs",
  "cvSource.help":
    "Conecta una carpeta con CVs (PDF/Word). El agente los lee, los evalúa contra la descripción del cargo y crea los candidatos en esta búsqueda.",
  "cvSource.none": "Ninguna carpeta conectada todavía.",
  "cvSource.connect": "Conectar carpeta",
  "cvSource.change": "Cambiar carpeta",
  "cvSource.analyze": "Analizar CVs",
  "cvSource.analyzing": "Analizando…",
  "cvSource.prompt": "Ruta de la carpeta de CVs:",
  "cvSource.connected": "Carpeta conectada",
  "cvSource.connectError": "No se pudo conectar la carpeta",
  "cvSource.analyzeStarted":
    "Análisis iniciado — el agente está leyendo los CVs; los candidatos irán apareciendo en Candidatos.",
  "cvSource.analyzeError": "No se pudo iniciar el análisis",
  "cvSource.needFolder": "Conecta una carpeta primero",

  // ---- Conectar fuente externa de CVs (HRO: agente conector) ----
  "connect.button": "Conectar fuente externa",
  "connect.dialogTitle": "Conectar una fuente de CVs",
  "connect.dialogDescription":
    "Trae los CVs desde donde estén: una carpeta sincronizada de Drive/OneDrive, una API como Pandapé, o una web. El agente arma la integración y deja los CVs en esta búsqueda.",
  "connect.typeLabel": "Tipo",
  "connect.type.drive": "Google Drive / OneDrive (carpeta sincronizada)",
  "connect.type.api": "API / Pandapé",
  "connect.type.web": "Web / personalizada",
  "connect.driveNote":
    "Elige la carpeta donde Drive/OneDrive sincroniza los CVs. Se usa el mismo flujo de carpeta local: una vez sincronizada, el agente la lee directo.",
  "connect.drivePick": "Elegir carpeta sincronizada",
  "connect.goalLabel": "¿Qué quieres traer?",
  "connect.goalPlaceholder":
    "Trae los CVs de la vacante 'Promotor SKF' de Pandapé",
  "connect.credentialsLabel": "Credenciales / token",
  "connect.credentialsHint": "opcional",
  "connect.credentialsPlaceholder":
    "Pega tu token de Pandapé o el JSON de credenciales",
  "connect.credentialsSecurity":
    "Tu token se guarda solo en tu equipo, no se envía a ningún lado salvo a la herramienta que conectas.",
  "connect.submit": "Construir y traer CVs",
  "connect.submitting": "Iniciando conector…",
  "connect.started":
    "Conector iniciado — el agente está armando la integración. Cuando termine, los CVs estarán en esta búsqueda y podrás darle Analizar CVs.",
  "connect.error": "No se pudo iniciar el conector",
  "connect.needGoal": "Describe qué quieres traer",
  "connect.cancel": "Cancelar",

  // ---- Filtros de Candidatos / Prospectos (pipeline) ----
  "candidates.filter.search": "Búsqueda",
  "candidates.filter.project": "Proyecto",
  "candidates.filter.allSearches": "Todas las búsquedas",
  "candidates.filter.allProjects": "Todos los proyectos",
  "candidates.filter.searchPlaceholder": "Buscar candidato…",
  "candidates.filter.searchLeadPlaceholder": "Buscar prospecto…",
  "candidates.noSearch": "Sin búsqueda",
  "candidates.field.search": "Búsqueda",
  "candidates.field.searchHint": "opcional · liga el candidato a una búsqueda",
  "candidates.field.project": "Proyecto",
  "candidates.field.none": "Ninguna",

  // ---- Onboarding hero ----
  "onboarding.tag": "Bienvenida a Rugol",
  "onboarding.headline": "Tu orquestador de agentes.",
  "onboarding.headlineHighlight": "Apoyo para las decisiones que importan.",
  "onboarding.pitch":
    "Rugol es tu sala de control de agentes. No piensas \"qué agente creo\" — piensas \"qué quiero resolver\": tu marca, tu día a día, ayudar a tu hija a estudiar, tu pipeline comercial. El equipo de agentes hace el trabajo y desafía tu pensamiento; tú decides con un mejor proceso, no solo con más información.",
  "onboarding.question": "¿Por dónde te gustaría empezar?",
  "onboarding.seeTemplates": "Ver los 5 templates",
  "onboarding.orArchitect": "o descríbelo en una línea con Architect →",
  "onboarding.localFirst": "Local-first.",
  "onboarding.localFirstDesc": "Todo corre en tu PC. Tus datos no salen.",
  "onboarding.mission": "Misión por proyecto.",
  "onboarding.missionDesc": "Cada equipo lee su porqué antes de cada tarea.",
  "onboarding.lessons": "Lecciones vivas.",
  "onboarding.lessonsDesc": "Lo que el equipo aprende queda como anclaje permanente.",
  "onboarding.advocate": "Abogado del diablo.",
  "onboarding.advocateDesc": "Para las decisiones que importan, dos perspectivas.",

  // ---- Template catalog ----
  "templates.title": "Empezar desde un template",
  "templates.description":
    "Cinco proyectos listos para clonar — desde la mamá que arma juegos para su hija hasta el founder que cuida su pipeline. Haz click, personaliza lo que quieras, deploya.",
  "templates.audienceCasual": "Día a día",
  "templates.audiencePro": "Profesional",
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
  "newProject.namePlaceholder": "Marca personal",
  "newProject.shortDescription": "Descripción corta",
  "newProject.shortDescriptionHint": "una sola línea para la tarjeta",
  "newProject.shortDescriptionPlaceholder": "Equipo que cuida mi voz pública en LinkedIn y X.",
  "newProject.mission": "Misión",
  "newProject.missionHint": "el porqué que el equipo lee antes de cada tarea",
  "newProject.missionPlaceholder":
    "Construir credibilidad técnica honesta. Publicar 3 piezas por semana centradas en lo que aprendí en producción. Nunca hype.",
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
    "Configura tokens y rutas desde aquí. Los cambios reinician en caliente los adapters y el watcher — sin tocar el backend.",
  "settings.refreshStatus": "Refrescar estado",
  "settings.dangerZone": "Zona peligrosa",
  "settings.dangerZoneDescription":
    "Restablecer la instalación a estado fresco — útil cuando vas a llevar la app a otro PC o quieres empezar limpio. Después del reset hay que reiniciar el backend (uvicorn) para que se recreen las tablas vacías. El proyecto Workspace y los 5 templates curados siguen disponibles.",
  "settings.resetButton": "Restablecer instalación",
  "settings.resetting": "Reseteando…",

  // ---- Settings · Entrevistas por voz (ElevenLabs) ----
  "settings.elevenlabs.title": "Entrevistas por voz · Sofía (ElevenLabs)",
  "settings.elevenlabs.body":
    "Pega tu API key de ElevenLabs y el Agent ID de tu entrevistadora. Se guarda solo en tu equipo.",
  "settings.elevenlabs.apiKey": "API key",
  "settings.elevenlabs.apiKeyHint": "se guarda solo en tu equipo",
  "settings.elevenlabs.agentId": "Agent ID",
  "settings.elevenlabs.configured": "configurado",
  "settings.elevenlabs.notConfigured": "sin configurar",
  "settings.elevenlabs.saved": "Ajustes de voz guardados",

  // ---- Settings · Telegram ----
  "settings.telegram.title": "Telegram",
  "settings.telegram.body":
    "Pega el token de @BotFather y listo: el bot empieza a responder al instante. No necesita nada más — cualquiera que le escriba habla con tu asistente.",
  "settings.telegram.connected": "conectado",
  "settings.telegram.configuredNotRunning": "configurado · sin iniciar",
  "settings.telegram.notConfigured": "sin configurar",
  "settings.telegram.tokenLabel": "Token del bot",
  "settings.telegram.tokenHintCurrent": "token actual {hint}",
  "settings.telegram.tokenHintNone": "sin token guardado",
  "settings.telegram.tokenPlaceholderSet":
    "(déjalo en blanco para mantener el actual; escribe uno nuevo para reemplazar)",
  "settings.telegram.save": "Guardar e iniciar",
  "settings.telegram.saving": "Guardando…",

  // ---- Architect ----
  "architect.title": "Architect",
  "architect.description":
    "Describe el resultado que quieres. Rugol propone un equipo pequeño de agentes, las skills que comparten, los schedules que los disparan y las semillas de ontología que los conectan. Revisa cada pieza, edita lo que quieras, y deploya.",
  "architect.startOver": "Empezar de nuevo",
  "architect.idea": "Tu idea",
  "architect.ideaHint": "una o dos oraciones en lenguaje cotidiano",
  "architect.constraints": "Restricciones",
  "architect.constraintsHint": "opcional · cadencia, canales, qué NO incluir",
  "architect.propose": "Proponer arquitectura",
  "architect.designing": "Diseñando…",
  "architect.deploy": "Deployar",

  // ---- Project / Search detail (HRO usa "Búsqueda") ----
  "projectDetail.deleted": "Proyecto eliminado",
  "searchDetail.deleted": "Búsqueda eliminada",
  "projectDetail.deleteFailed": "No se pudo eliminar",
  "projectDetail.loading": "Cargando proyecto…",
  "searchDetail.loading": "Cargando búsqueda…",
  "projectDetail.notFound": "Proyecto no encontrado.",
  "searchDetail.notFound": "Búsqueda no encontrada.",
  "projectDetail.deleteConfirm": "¿Eliminar el proyecto \"{name}\"? Solo es posible si no tiene agentes.",
  "searchDetail.deleteConfirm": "¿Eliminar la búsqueda \"{name}\"? Solo es posible si no tiene agentes.",
  "projectDetail.moveAgentsFirst": "Mueve los agentes primero",
  "projectDetail.deleteTitle": "Eliminar proyecto",
  "searchDetail.deleteTitle": "Eliminar búsqueda",
  "projectDetail.noDescription": "(sin descripción)",
  "projectDetail.statAgents": "Agentes",
  "projectDetail.statStatus": "Estado",
  "projectDetail.tabTeam": "Equipo",
  "projectDetail.tabLessons": "Lecciones",
  "projectDetail.tabRuns": "Runs recientes",
  "projectDetail.teamHeading": "Plantilla del proyecto",
  "searchDetail.teamHeading": "Equipo de la búsqueda",
  "projectDetail.addArchitect": "Sumar con Architect",
  "projectDetail.newAgent": "Nuevo agente",
  "projectDetail.teamEmpty": "Este proyecto todavía no tiene agentes asignados.",
  "searchDetail.teamEmpty": "Esta búsqueda todavía no tiene agentes asignados.",
  "projectDetail.teamEmptyHint":
    "Usa Architect para diseñar el equipo a partir de una idea, o crea uno manualmente y elige este proyecto.",
  "searchDetail.teamEmptyHint":
    "Usa Architect para diseñar el equipo a partir de una idea, o crea uno manualmente y elige esta búsqueda.",
  "projectDetail.runsHeading": "Últimos {n} runs",
  "projectDetail.runsEmpty": "Todavía no hay runs en este proyecto.",
  "searchDetail.runsEmpty": "Todavía no hay runs en esta búsqueda.",
  "projectDetail.edit": "Editar",
  "projectDetail.editTitle": "Editar {name}",
  "projectDetail.editDescription": "Los cambios se guardan en la base de datos. El slug es inmutable.",
  "projectDetail.fieldName": "Nombre",
  "projectDetail.fieldShortDesc": "Descripción corta",
  "projectDetail.fieldIcon": "Ícono",
  "projectDetail.fieldColor": "Color",
  "projectDetail.updated": "Proyecto actualizado",
  "searchDetail.updated": "Búsqueda actualizada",
  "projectDetail.updateFailed": "No se pudo actualizar",
  "projectDetail.mission": "Misión",
  "projectDetail.saving": "Guardando…",

  // ---- Lecciones vivas ----
  "lessons.heading": "Lecciones vivas del proyecto",
  "lessons.headingSearch": "Lecciones vivas de la búsqueda",
  "lessons.description":
    "Cada agente del equipo lee esta lista antes de cada run. Funciona como anclaje: lo que el equipo aprendió de la mala, las decisiones tomadas, los sesgos detectados. Piénsalo como las \"reglas de la casa\" — no más de 10-15 ítems o pierde foco.",
  "lessons.newLesson": "Nueva lección",
  "lessons.newLessonHint": "qué tipo de aprendizaje es",
  "lessons.placeholder": "ej: \"El cliente Acme prefiere correos cortos sin asunto en mayúsculas\"",
  "lessons.type": "Tipo",
  "lessons.add": "Agregar",
  "lessons.saved": "Lección guardada",
  "lessons.saveFailed": "No se pudo guardar",
  "lessons.deleteFailed": "No se pudo borrar",
  "lessons.empty": "Todavía no hay lecciones registradas para este proyecto.",
  "lessons.emptySearch": "Todavía no hay lecciones registradas para esta búsqueda.",
  "lessons.emptyHint":
    "Empieza con 2-3 reglas que el equipo nunca debería romper. Las siguientes van a aparecer cuando apruebes propuestas de mejora (Improvements) y las promuevas a lección.",
  "lessons.delete": "Borrar",

  // ---- Common ----
  "common.loading": "Cargando…",
  "common.error": "Error",
  "common.save": "Guardar",
  "common.delete": "Borrar",
  "common.cancel": "Cancelar",
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
  "nav.memoryGraph": "Memory",
  "nav.antFarm": "Ant farm",
  "nav.ontology": "Ontology",
  "nav.improvements": "Improvements",
  "nav.settings": "Settings",
  "nav.pipelineLead": "Prospects",
  "nav.pipelineCandidate": "Candidates",
  "nav.interviews": "Interviews",
  "nav.home": "Home",
  "nav.guide": "How it works",
  "nav.searches": "Searches",

  // ---- Nav · sections (HRO / CRM) ----
  "nav.section.recruitment": "Recruitment",
  "nav.section.prospecting": "Prospecting",
  "nav.section.agentBrain": "Agent brain",
  "nav.section.configuration": "Configuration",

  // ---- Guide "How it works" ----
  "guide.hro.title": "How Rugol HRO works",
  "guide.hro.subtitle":
    "From a candidate who arrives to a recommended shortlist, without you lifting an extra finger.",
  "guide.crm.title": "How Rugol CRM works",
  "guide.crm.subtitle":
    "From an ideal profile to a qualified prospect ready for you to close.",
  "guide.rugol.title": "How Rugol works",
  "guide.rugol.body":
    "Rugol is your agent control room. You describe an outcome in Architect, it proposes a team of agents with their mission, skills and rituals, and you run them from Projects and Operations. The team does the work and challenges your thinking; you keep the decision.",
  "guide.flowHeading": "The flow, step by step",

  // HRO steps
  "guide.hro.s1.title": "Candidate arrives",
  "guide.hro.s1.body": "From Pandapé or via your interview link.",
  "guide.hro.s2.title": "Screening",
  "guide.hro.s2.body": "The agent scores the CV against the search profile.",
  "guide.hro.s3.title": "Sofía interviews",
  "guide.hro.s3.body": "Voice interview, with six competencies scored on a BARS scale.",
  "guide.hro.s4.title": "Automatic pipeline",
  "guide.hro.s4.body": "The interview is scored and the candidate enters the board on its own.",
  "guide.hro.s5.title": "Shortlist",
  "guide.hro.s5.body": "The recommended top 3 is built for you to decide.",

  // CRM steps
  "guide.crm.s1.title": "You define the ICP",
  "guide.crm.s1.body": "Your ideal customer profile and the value proposition.",
  "guide.crm.s2.title": "Hunter searches",
  "guide.crm.s2.body": "Generates and enriches leads from the connected sources.",
  "guide.crm.s3.title": "Researcher digs in",
  "guide.crm.s3.body": "Gathers context on each prospect before reaching out.",
  "guide.crm.s4.title": "Closer writes",
  "guide.crm.s4.body": "Drafts personalized outreach and converses across channels.",
  "guide.crm.s5.title": "Strategist qualifies",
  "guide.crm.s5.body": "Scores by ICP and BANT, and prospects enter the board.",

  // "Where each thing is configured" table
  "guide.config.heading": "Where each thing is configured",
  "guide.config.thing": "What",
  "guide.config.where": "Where",
  "guide.config.anthropic.thing": "Anthropic account",
  "guide.config.anthropic.where": "Onboarding",
  "guide.config.elevenlabs.thing": "ElevenLabs · Sofía",
  "guide.config.elevenlabs.where": "Settings → Voice interviews",
  "guide.config.telegram.thing": "Telegram",
  "guide.config.telegram.where": "Settings → just the token",
  "guide.config.tools.thing": "Per-agent tools · MCP",
  "guide.config.tools.where": "Agents → open the agent → Tools / MCP",

  // Interview link box
  "guide.link.heading": "Interview link",
  "guide.link.body": "Share this link to interview a candidate.",
  "guide.link.copy": "Copy",
  "guide.link.open": "Open",
  "guide.link.copied": "Link copied",
  "guide.link.copyFailed": "Couldn't copy",

  // "Where you see each thing"
  "guide.see.heading": "Where you see each thing",
  "guide.see.candidates.title": "Candidates",
  "guide.see.candidates.body": "The kanban board for your hiring pipeline.",
  "guide.see.interviews.title": "Interviews",
  "guide.see.interviews.body": "Sofía's reports with the BARS competencies.",
  "guide.see.searches.title": "Searches",
  "guide.see.searches.body": "Each position to fill with its job description.",
  "guide.see.agents.title": "Agents",
  "guide.see.agents.body": "The agent brain: how it thinks and which tools it uses.",
  "guide.see.prospects.title": "Prospects",
  "guide.see.prospects.body": "The kanban board for your sales pipeline.",
  "guide.see.projects.title": "Projects",
  "guide.see.projects.body": "Each initiative with its mission and agent team.",

  // ---- Pipeline (CRM prospects / HRO candidates) ----
  "pipeline.titleLead": "Prospects",
  "pipeline.titleCandidate": "Candidates",
  "pipeline.descLead":
    "Live sales pipeline. Your agents register and move prospects through the stages; you decide and close.",
  "pipeline.descCandidate":
    "Live hiring pipeline. Your agents register and move candidates through the stages; you make the hire.",
  "pipeline.add": "Add",
  "pipeline.addLead": "Add prospect",
  "pipeline.addCandidate": "Add candidate",
  "pipeline.loading": "Loading pipeline…",
  "pipeline.emptyLead":
    "No prospects yet. Your agents will register them here as they work, or add them manually.",
  "pipeline.emptyCandidate":
    "No candidates yet. Your agents will register them here as they work, or add them manually.",
  "pipeline.colEmpty": "No items",
  "pipeline.rugolTitle": "This view belongs to Rugol CRM / HRO",
  "pipeline.rugolBody":
    "The domain pipeline lives in the CRM (prospects) and HRO (candidates) variants. In Rugol you orchestrate your agents from Projects and Operations.",
  "pipeline.score": "Score",
  "pipeline.noScore": "no score",
  "pipeline.source": "Source",
  "pipeline.manual": "manual",
  "pipeline.details": "Details",
  "pipeline.data": "Data",
  "pipeline.noData": "No structured data.",
  "pipeline.history": "History",
  "pipeline.noNotes": "No notes recorded yet.",
  "pipeline.addNote": "Add note",
  "pipeline.notePlaceholder": "Write a note…",
  "pipeline.saveNote": "Save note",
  "pipeline.savingNote": "Saving…",
  "pipeline.delete": "Delete item",
  "pipeline.deleteConfirm": "Delete this item from the pipeline?",
  "pipeline.moveBack": "Previous stage",
  "pipeline.moveForward": "Next stage",
  "pipeline.title": "Title",
  "pipeline.titlePlaceholder": "Prospect / candidate name",
  "pipeline.subtitle": "Subtitle",
  "pipeline.subtitlePlaceholder": "Company, role, short detail",
  "pipeline.stage": "Stage",
  "pipeline.cancel": "Cancel",
  "pipeline.create": "Create",
  "pipeline.creating": "Creating…",
  "pipeline.created": "Item created",
  "pipeline.deleted": "Item deleted",
  "pipeline.noteAdded": "Note added",
  "pipeline.moved": "Item moved",

  // ---- Interviews (Sofía / HRO) ----
  "interviews.title": "Interviews",
  "interviews.desc":
    "Sofía's interview reports. Each assessed candidate carries a verdict, the six competencies with their scores, and the cited evidence.",
  "interviews.loading": "Loading interviews…",
  "interviews.empty":
    "No interviews yet. Once Sofía interviews candidates, her reports will show up here.",
  "interviews.notHroTitle": "This view belongs to Rugol HRO",
  "interviews.notHroBody":
    "Sofía's interviews only apply to the hiring variant (HRO).",
  "interviews.verdict": "Verdict",
  "interviews.verdict.avanzar": "Advance",
  "interviews.verdict.dudoso": "On the fence",
  "interviews.verdict.descartar": "Reject",
  "interviews.confidence": "Confidence",
  "interviews.confidence.alta": "high",
  "interviews.confidence.media": "medium",
  "interviews.confidence.baja": "low",
  "interviews.competencies": "Competencies",
  "interviews.noScore": "n/a",
  "interviews.evidence": "Evidence",
  "interviews.noEvidence": "No evidence cited.",
  "interviews.risks": "Risks",
  "interviews.noRisks": "No risks flagged.",
  "interviews.history": "History",
  "interviews.noNotes": "No notes recorded yet.",
  "interviews.manual": "manual",
  "interviews.expand": "View detail",
  "interviews.collapse": "Hide detail",
  "interviews.count": "interviews",

  // ---- In-app interview with Sofía (text) ----
  "interviews.live.start": "Interview with Sofía",
  "interviews.live.title": "Interview with Sofía",
  "interviews.live.intro":
    "Sofía runs the interview right here: she asks one thing at a time, you type the candidate's answer. When you close, she scores it with BARS and registers it in the pipeline.",
  "interviews.live.candidateName": "Candidate name",
  "interviews.live.candidateNamePlaceholder": "María López",
  "interviews.live.role": "Role / seniority",
  "interviews.live.rolePlaceholder": "Retail promoter",
  "interviews.live.search": "Search",
  "interviews.live.searchHint": "Sofía uses the job description of this search",
  "interviews.live.noSearch": "No search",
  "interviews.live.begin": "Begin interview",
  "interviews.live.candidatePlaceholder": "Type the candidate's answer…",
  "interviews.live.send": "Send",
  "interviews.live.thinking": "Sofía is thinking…",
  "interviews.live.finish": "Finish & evaluate",
  "interviews.live.finishing": "Evaluating…",
  "interviews.live.scored": "Interview evaluated and registered in the pipeline",
  "interviews.live.scoreError": "Couldn't evaluate the interview",
  "interviews.live.turnError": "Sofía couldn't respond",
  "interviews.live.needName": "Enter the candidate's name first",
  "interviews.live.you": "Candidate",
  "interviews.live.sofia": "Sofía",
  "interviews.live.minTurns": "Answer at least a couple of questions before evaluating.",
  "interviews.live.close": "Close",
  "interviews.live.restart": "Restart",

  // ---- Voice Sofía (ElevenLabs) ----
  "voice.sync": "Sync with ElevenLabs",
  "voice.syncing": "Syncing…",
  "voice.syncDone": "{n} new interview(s)",
  "voice.syncNone": "No new interviews",
  "voice.syncError": "Sync failed",
  "voice.notConfigured":
    "Connect your ElevenLabs account in Settings to pull Sofía's interviews.",
  "voice.goToSettings": "Go to Settings",
  "voice.launch": "Launch voice interview",

  // ---- HRO Cockpit (recruiting room — home) ----
  "hro.cockpit.tag": "Recruiting room",
  "hro.cockpit.title": "Recruiting room",
  "hro.cockpit.subtitle":
    "Your agents assess, Sofía interviews, and everything sorts itself into your pipeline.",
  "hro.cockpit.stat.candidates": "candidates",
  "hro.cockpit.stat.interviews": "interviews done",

  // Flow (5 steps)
  "hro.cockpit.flow.heading": "How it works, end to end",
  "hro.cockpit.flow.s1.title": "Candidate arrives",
  "hro.cockpit.flow.s1.body": "From Pandapé or via your interview link.",
  "hro.cockpit.flow.s2.title": "Screening",
  "hro.cockpit.flow.s2.body": "hro-screener filters and ranks by role fit.",
  "hro.cockpit.flow.s3.title": "Sofía interviews",
  "hro.cockpit.flow.s3.body": "Voice interview, with BARS scoring.",
  "hro.cockpit.flow.s4.title": "Automatic pipeline",
  "hro.cockpit.flow.s4.body": "Each candidate moves through the stages on its own.",
  "hro.cockpit.flow.s5.title": "Shortlist",
  "hro.cockpit.flow.s5.body": "hro-matcher builds the final shortlist for you.",

  // Connections
  "hro.cockpit.connections.heading": "What's connected",
  "hro.cockpit.connections.active": "active",
  "hro.cockpit.connections.connected": "connected",
  "hro.cockpit.connections.missing": "needs setup",
  "hro.cockpit.connections.notRunning": "configured · not running",
  "hro.cockpit.connections.notConnected": "not connected",
  "hro.cockpit.connections.configure": "Configure",
  "hro.cockpit.connections.anthropic.name": "Anthropic",
  "hro.cockpit.connections.anthropic.body":
    "The brain behind your agents. Included in your subscription.",
  "hro.cockpit.connections.elevenlabs.name": "ElevenLabs · Sofía",
  "hro.cockpit.connections.elevenlabs.body":
    "Sofía's voice for interviewing candidates.",
  "hro.cockpit.connections.telegram.name": "Telegram",
  "hro.cockpit.connections.telegram.body":
    "Get alerts and run the pipeline from your phone.",

  // Interview link
  "hro.cockpit.link.heading": "Interview link",
  "hro.cockpit.link.body": "Share this link to interview a candidate.",
  "hro.cockpit.link.copy": "Copy",
  "hro.cockpit.link.open": "Open",
  "hro.cockpit.link.copied": "Link copied",
  "hro.cockpit.link.copyFailed": "Couldn't copy",

  // Quick actions
  "hro.cockpit.actions.heading": "Quick actions",
  "hro.cockpit.actions.candidates.title": "View candidates",
  "hro.cockpit.actions.candidates.body": "Your live hiring pipeline.",
  "hro.cockpit.actions.interviews.title": "View interviews",
  "hro.cockpit.actions.interviews.body": "The reports Sofía left behind.",
  "hro.cockpit.actions.sync.title": "Sync interviews",
  "hro.cockpit.actions.sync.body": "Pull the latest interviews from ElevenLabs.",
  "hro.cockpit.actions.configureSofia.title": "Configure Sofía",
  "hro.cockpit.actions.configureSofia.body": "Tune your voice interviewer.",

  // ---- Copilot (HRO home) ----
  "hro.copilot.name": "Copilot",
  "hro.copilot.title": "Your recruiting copilot",
  "hro.copilot.subtitle":
    "Ask in plain language: open a search, screen CVs, recommend candidates. It coordinates the team and brings you results — you decide.",
  "hro.copilot.ex1": "I have a retail promoter opening in Maipú. What do you need from me?",
  "hro.copilot.ex2": "Recommend candidates from my pipeline for a promoter position.",
  "hro.copilot.ex3": "Screen the CVs from my latest search and build the ranking.",
  "hro.copilot.ex4": "Who should I interview first, and why?",
  "hro.copilot.unavailable":
    "The copilot is getting ready. If it doesn't show up, check that the 'assistant' agent exists in Agents.",

  // ---- Funnel with agents (what each one does) ----
  "hro.funnel.heading": "The team your copilot coordinates",
  "hro.funnel.note":
    "You talk to the copilot in plain language; it decides and coordinates this team. It's not a rigid A→B flow — it adapts to what you ask.",
  "hro.funnel.driver": "Done by",
  "hro.funnel.s1.title": "CVs arrive",
  "hro.funnel.s1.body": "From your sources (Pandapé, job boards, Drive, folder) or the interview link.",
  "hro.funnel.s1.agent": "Connector",
  "hro.funnel.s2.title": "Screening",
  "hro.funnel.s2.body": "Scores each CV against the profile, 1-5 with evidence.",
  "hro.funnel.s2.agent": "Screener",
  "hro.funnel.s3.title": "Hard filter",
  "hro.funnel.s3.body": "Applies the non-negotiable requirements (location, availability).",
  "hro.funnel.s3.agent": "Knockout",
  "hro.funnel.s4.title": "Interview",
  "hro.funnel.s4.body": "Sofía runs a competency interview (BARS) and leaves her report.",
  "hro.funnel.s4.agent": "Sofía",
  "hro.funnel.s5.title": "Shortlist",
  "hro.funnel.s5.body": "Compares the interviewed and builds the recommended top 3.",
  "hro.funnel.s5.agent": "Matcher",
  "hro.funnel.s6.title": "Offer",
  "hro.funnel.s6.body": "Drafts the message to the chosen one and to those not selected.",
  "hro.funnel.s6.agent": "Offer",

  // ---- CV sources ----
  "cvSources.title": "CV sources",
  "cvSources.subtitle": "Where your copilot pulls candidates from. Add the ones you use: the agent builds the integration and fills your pipeline.",
  "cvSources.empty": "No sources connected yet. Add one so your copilot can bring candidates.",
  "cvSources.add": "Add source",
  "cvSources.adding": "Adding…",
  "cvSources.type": "Source type",
  "cvSources.name": "Name (optional)",
  "cvSources.namePlaceholder": "e.g. Pandapé — retail account",
  "cvSources.credentials": "Token / credentials",
  "cvSources.credentialsOptional": "optional",
  "cvSources.credentialsPlaceholder": "Paste the token or user:password",
  "cvSources.added": "Source added",
  "cvSources.addError": "Couldn't add the source",
  "cvSources.remove": "Remove",
  "cvSources.removed": "Source removed",
  "cvSources.removeError": "Couldn't remove",
  "cvSources.connected": "configured",
  "cvSources.secure": "Your token is stored only on your machine.",

  // ---- Onboarding Install → Configure → Enjoy ----
  "onboarding.wizard.tag": "Welcome",
  "onboarding.wizard.title": "Let's get your recruiting running",
  "onboarding.wizard.subtitle": "Three steps and you're set. You can change it later in Settings.",
  "onboarding.wizard.step": "Step",
  "onboarding.wizard.of": "of",
  "onboarding.wizard.next": "Next",
  "onboarding.wizard.back": "Back",
  "onboarding.wizard.skip": "Skip for now",
  "onboarding.wizard.finish": "Get started",
  "onboarding.wizard.finishing": "Done…",
  "onboarding.wizard.done": "All set! Your copilot is live.",
  "onboarding.anthropic.title": "Your brain: Anthropic",
  "onboarding.anthropic.body": "Your copilot and agents think with your Anthropic account. It's already included in this app — nothing to do here.",
  "onboarding.anthropic.ok": "Connected via your subscription",
  "onboarding.telegram.title": "Run it from your phone: Telegram",
  "onboarding.telegram.body": "Paste your bot token from @BotFather and you'll be able to ask your copilot from your phone. Optional.",
  "onboarding.eleven.title": "Voice interviews: Sofía",
  "onboarding.eleven.body": "Connect your ElevenLabs account so Sofía interviews by voice. Optional — it also works by text.",
  "onboarding.eleven.key": "ElevenLabs API key",
  "onboarding.eleven.agent": "Agent ID",
  "onboarding.sources.title": "Where do we get candidates?",
  "onboarding.sources.body": "Connect at least one CV source (Pandapé, Chiletrabajo, Computrabajo, Drive or a folder). You can add more later.",
  "onboarding.saved": "Settings saved",

  // ---- Memory graph ----
  "memgraph.title": "Memory network",
  "memgraph.desc":
    "Your agents' neural network, Obsidian-style: every node is a memory or a concept; the lines are the [[links]] they weave as they learn.",
  "memgraph.search": "Search memory or concept…",
  "memgraph.allAgents": "All agents",
  "memgraph.agents": "agents",
  "memgraph.memories": "memories",
  "memgraph.concepts": "concepts",
  "memgraph.links": "links",
  "memgraph.kind.agent": "agent",
  "memgraph.kind.user": "user",
  "memgraph.kind.feedback": "feedback",
  "memgraph.kind.project": "project",
  "memgraph.kind.reference": "reference",
  "memgraph.kind.note": "note",
  "memgraph.kind.concept": "concept",
  "memgraph.emptyTitle": "No memories yet",
  "memgraph.emptyBody":
    "Talk to an agent (Telegram or chat) and come back: everything it learns shows up here as a node, and its connections weave the network.",
  "memgraph.panel.agent": "Agent — the hub of its own memory cluster.",
  "memgraph.panel.concept": "Concept — a [[link]] that isn't a memory yet. It connects whoever mentions it.",
  "memgraph.panel.degree": "Connections",
  "memgraph.hint":
    "Drag nodes · wheel to zoom · click a node to read the memory · click empty space to deselect.",

  // ---- Projects home ----
  "projects.title": "Projects",
  "projects.description":
    "Each project brings together a team of agents with its own mission. They do the work and challenge your thinking; you keep the decision.",
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

  // ---- Searches (HRO: a project IS a position to fill) ----
  "searches.title": "Searches",
  "searches.description":
    "Each search is a position to fill, with its job description and its agent team. They assess and interview; you make the hire.",
  "searches.newSearch": "New search",
  "searches.empty": "You don't have any searches yet",
  "searches.emptyDescription":
    "Create a search to open a position — describe the role and let your agents assess the candidates.",
  "searches.activeStat": "Active searches",
  "newSearch.title": "New search",
  "newSearch.description":
    "Define the position to fill. Your agents read the scope and the job description before assessing each candidate.",
  "newSearch.name": "Position name",
  "newSearch.namePlaceholder": "Senior Data Analyst",
  "newSearch.create": "Create search",
  "project.jobDescription": "Job description",
  "project.jobDescriptionHint": "the profile the agent uses to assess candidates",
  "project.jobDescriptionPlaceholder":
    "Responsibilities, requirements, key competencies and everything that defines the role profile.",
  "project.scope": "Scope / objective",
  "project.scopeHint": "the why the team reads before every task",
  "project.noJobDescription": "No job description yet.",

  // ---- CV source (HRO: CV folder per search) ----
  "cvSource.title": "CV source",
  "cvSource.help":
    "Connect a folder with CVs (PDF/Word). The agent reads them, scores them against the job description and creates the candidates in this search.",
  "cvSource.none": "No folder connected yet.",
  "cvSource.connect": "Connect folder",
  "cvSource.change": "Change folder",
  "cvSource.analyze": "Analyze CVs",
  "cvSource.analyzing": "Analyzing…",
  "cvSource.prompt": "Path to the CV folder:",
  "cvSource.connected": "Folder connected",
  "cvSource.connectError": "Couldn't connect the folder",
  "cvSource.analyzeStarted":
    "Analysis started — the agent is reading the CVs; candidates will show up in Candidates.",
  "cvSource.analyzeError": "Couldn't start the analysis",
  "cvSource.needFolder": "Connect a folder first",

  // ---- Connect external CV source (HRO: connector agent) ----
  "connect.button": "Connect external source",
  "connect.dialogTitle": "Connect a CV source",
  "connect.dialogDescription":
    "Bring CVs from wherever they are: a synced Drive/OneDrive folder, an API like Pandapé, or a website. The agent builds the integration and drops the CVs into this search.",
  "connect.typeLabel": "Type",
  "connect.type.drive": "Google Drive / OneDrive (synced folder)",
  "connect.type.api": "API / Pandapé",
  "connect.type.web": "Web / custom",
  "connect.driveNote":
    "Choose the folder where Drive/OneDrive syncs the CVs. It uses the same local-folder flow: once synced, the agent reads it directly.",
  "connect.drivePick": "Choose synced folder",
  "connect.goalLabel": "What do you want to bring?",
  "connect.goalPlaceholder":
    "Bring the CVs from the 'SKF Promoter' opening on Pandapé",
  "connect.credentialsLabel": "Credentials / token",
  "connect.credentialsHint": "optional",
  "connect.credentialsPlaceholder":
    "Paste your Pandapé token or the credentials JSON",
  "connect.credentialsSecurity":
    "Your token is stored only on your machine; it's never sent anywhere except to the tool you connect.",
  "connect.submit": "Build and bring CVs",
  "connect.submitting": "Starting connector…",
  "connect.started":
    "Connector started — the agent is building the integration. When it finishes, the CVs will be in this search and you can hit Analyze CVs.",
  "connect.error": "Couldn't start the connector",
  "connect.needGoal": "Describe what you want to bring",
  "connect.cancel": "Cancel",

  // ---- Candidates / Prospects filters (pipeline) ----
  "candidates.filter.search": "Search",
  "candidates.filter.project": "Project",
  "candidates.filter.allSearches": "All searches",
  "candidates.filter.allProjects": "All projects",
  "candidates.filter.searchPlaceholder": "Find candidate…",
  "candidates.filter.searchLeadPlaceholder": "Find prospect…",
  "candidates.noSearch": "No search",
  "candidates.field.search": "Search",
  "candidates.field.searchHint": "optional · links the candidate to a search",
  "candidates.field.project": "Project",
  "candidates.field.none": "None",

  // ---- Onboarding hero ----
  "onboarding.tag": "Welcome to Rugol",
  "onboarding.headline": "Your agent orchestrator.",
  "onboarding.headlineHighlight": "Support for the decisions that matter.",
  "onboarding.pitch":
    "Rugol is your agent control room. You don't think \"which agent should I create\" — you think \"what do I want to get done\": your brand, your day-to-day, helping your daughter study, your sales pipeline. The agent team does the work and challenges your thinking; you decide with a better process, not just more information.",
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

  // ---- Settings · Voice interviews (ElevenLabs) ----
  "settings.elevenlabs.title": "Voice interviews · Sofía (ElevenLabs)",
  "settings.elevenlabs.body":
    "Paste your ElevenLabs API key and your interviewer's Agent ID. It's stored only on your machine.",
  "settings.elevenlabs.apiKey": "API key",
  "settings.elevenlabs.apiKeyHint": "stored only on your machine",
  "settings.elevenlabs.agentId": "Agent ID",
  "settings.elevenlabs.configured": "configured",
  "settings.elevenlabs.notConfigured": "not configured",
  "settings.elevenlabs.saved": "Voice settings saved",

  // ---- Settings · Telegram ----
  "settings.telegram.title": "Telegram",
  "settings.telegram.body":
    "Paste the token from @BotFather and you're set: the bot starts replying instantly. Nothing else needed — anyone who messages it talks to your assistant.",
  "settings.telegram.connected": "connected",
  "settings.telegram.configuredNotRunning": "configured · not running",
  "settings.telegram.notConfigured": "not configured",
  "settings.telegram.tokenLabel": "Bot token",
  "settings.telegram.tokenHintCurrent": "current token {hint}",
  "settings.telegram.tokenHintNone": "no token saved",
  "settings.telegram.tokenPlaceholderSet":
    "(leave blank to keep the current one; type a new one to replace)",
  "settings.telegram.save": "Save & start",
  "settings.telegram.saving": "Saving…",

  // ---- Architect ----
  "architect.title": "Architect",
  "architect.description":
    "Describe the outcome you want. Rugol proposes a small team of agents, the skills they share, the schedules that drive them, and the ontology seeds that connect them. Review every piece, edit anything you want, and deploy.",
  "architect.startOver": "Start over",
  "architect.idea": "Your idea",
  "architect.ideaHint": "one or two sentences in plain language",
  "architect.constraints": "Constraints",
  "architect.constraintsHint": "optional · cadence, channels, what NOT to include",
  "architect.propose": "Propose architecture",
  "architect.designing": "Designing…",
  "architect.deploy": "Deploy",

  // ---- Project / Search detail (HRO uses "Search") ----
  "projectDetail.deleted": "Project deleted",
  "searchDetail.deleted": "Search deleted",
  "projectDetail.deleteFailed": "Couldn't delete",
  "projectDetail.loading": "Loading project…",
  "searchDetail.loading": "Loading search…",
  "projectDetail.notFound": "Project not found.",
  "searchDetail.notFound": "Search not found.",
  "projectDetail.deleteConfirm": "Delete the project \"{name}\"? Only possible if it has no agents.",
  "searchDetail.deleteConfirm": "Delete the search \"{name}\"? Only possible if it has no agents.",
  "projectDetail.moveAgentsFirst": "Move the agents first",
  "projectDetail.deleteTitle": "Delete project",
  "searchDetail.deleteTitle": "Delete search",
  "projectDetail.noDescription": "(no description)",
  "projectDetail.statAgents": "Agents",
  "projectDetail.statStatus": "Status",
  "projectDetail.tabTeam": "Team",
  "projectDetail.tabLessons": "Lessons",
  "projectDetail.tabRuns": "Recent runs",
  "projectDetail.teamHeading": "Project staff",
  "searchDetail.teamHeading": "Search team",
  "projectDetail.addArchitect": "Add with Architect",
  "projectDetail.newAgent": "New agent",
  "projectDetail.teamEmpty": "This project has no agents assigned yet.",
  "searchDetail.teamEmpty": "This search has no agents assigned yet.",
  "projectDetail.teamEmptyHint":
    "Use Architect to design the team from an idea, or create one manually and pick this project.",
  "searchDetail.teamEmptyHint":
    "Use Architect to design the team from an idea, or create one manually and pick this search.",
  "projectDetail.runsHeading": "Last {n} runs",
  "projectDetail.runsEmpty": "No runs in this project yet.",
  "searchDetail.runsEmpty": "No runs in this search yet.",
  "projectDetail.edit": "Edit",
  "projectDetail.editTitle": "Edit {name}",
  "projectDetail.editDescription": "Changes are saved to the database. The slug is immutable.",
  "projectDetail.fieldName": "Name",
  "projectDetail.fieldShortDesc": "Short description",
  "projectDetail.fieldIcon": "Icon",
  "projectDetail.fieldColor": "Color",
  "projectDetail.updated": "Project updated",
  "searchDetail.updated": "Search updated",
  "projectDetail.updateFailed": "Couldn't update",
  "projectDetail.mission": "Mission",
  "projectDetail.saving": "Saving…",

  // ---- Living lessons ----
  "lessons.heading": "Project living lessons",
  "lessons.headingSearch": "Search living lessons",
  "lessons.description":
    "Every agent on the team reads this list before each run. It works as an anchor: what the team learned the hard way, decisions made, biases spotted. Think of it as the \"house rules\" — no more than 10-15 items or it loses focus.",
  "lessons.newLesson": "New lesson",
  "lessons.newLessonHint": "what kind of learning it is",
  "lessons.placeholder": "e.g. \"Client Acme prefers short emails with no all-caps subject\"",
  "lessons.type": "Type",
  "lessons.add": "Add",
  "lessons.saved": "Lesson saved",
  "lessons.saveFailed": "Couldn't save",
  "lessons.deleteFailed": "Couldn't delete",
  "lessons.empty": "No lessons recorded for this project yet.",
  "lessons.emptySearch": "No lessons recorded for this search yet.",
  "lessons.emptyHint":
    "Start with 2-3 rules the team should never break. The next ones appear when you approve improvement proposals (Improvements) and promote them to a lesson.",
  "lessons.delete": "Delete",

  // ---- Common ----
  "common.loading": "Loading…",
  "common.error": "Error",
  "common.save": "Save",
  "common.delete": "Delete",
  "common.cancel": "Cancel",
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
