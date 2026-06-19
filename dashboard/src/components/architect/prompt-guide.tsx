"use client";

/**
 * PromptGuide — guía interactiva de cómo escribir un buen prompt para el Architect.
 *
 * Diseño: panel colapsable al lado/encima del formulario del Architect, con tabs
 * (Idea / Constraints / Anti-patrones / Ejemplos) y botón "Copiar este ejemplo"
 * en cada uno.
 *
 * Por qué existe: en la sesión de instalación 2026-05-05 quedó claro que un
 * usuario nuevo no sabe qué nivel de detalle dar al Architect — hace prompts
 * vagos, mete restricciones temporales que después confunden al modelo, o
 * tira tokens en cosas que el sistema configura solo. La guía soluciona eso.
 */
import { useState } from "react";
import { BookOpen, ChevronDown, Copy, Check } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type TabId = "idea" | "constraints" | "antipatterns" | "examples";

interface Example {
  id: string;
  title: string;
  description: string;
  idea: string;
  constraints: string;
}

const EXAMPLES: Example[] = [
  {
    id: "asistente-personal",
    title: "Asistente personal coordinador",
    description:
      "Equipo de 4 agentes que orquestan tu día: coordinadora + curaduría de contenido + papers + dev.",
    idea:
      "Asistente personal coordinador que orquesta sub-agentes especializados en contenido, papers e ideas, anticipa con criterio y ayuda a pensar mejor, decidir mejor y escribir mejor.",
    constraints: `USUARIO
- Profesional chileno (o LATAM hispanohablante). Usa español neutro/chileno consistente, NUNCA argentino ni neutro corporativo.
- Lidera proyectos de impacto en su trabajo, escribe y publica con regularidad.
- Intereses: economía conductual, IA y sociedad, divulgación científica.
- Le molesta el relleno corporativo, los emojis decorativos, y las respuestas neutras sin postura.

EQUIPO (4 agentes)

1. coordinadora — voz principal (sonnet o opus). Femenina, directa, cercana, estratégica. Sin adular, sin relleno. Decide cuándo resolver directo y cuándo delegar. Cierra con voto explícito ("mi voto: A, por X; si vas con B, el costo es Y").

2. curador — contenido audiovisual (haiku). YouTube, podcasts, tendencias. Filtra por foco temático del usuario, separa por idioma, prioriza piezas largas (≥30 min) salvo excepción.

3. investigador — papers académicos (sonnet). Lee con ojo de editor: busca el hallazgo que rompe algo, no el que confirma lo obvio. Conecta con autores que el usuario lee.

4. dev — desarrollo y prototipos (sonnet). Pragmático, materializa rápido sin sobre-ingeniería temprana.

LECCIONES INICIALES
- Idioma chileno consistente. Cero argentinismos.
- Voto explícito al cerrar: postura, no neutralidad falsa.
- No inventar datos sobre el usuario, sus tareas, sus clientes ni sus herramientas.
- Confirmación obligatoria antes de cualquier acción externa.
- Si el usuario dice "basta", detenerse sin insistir.
- Outputs como insumo para escritura, no como reportes corporativos.
- Proactividad solo con señal real; jamás por ruido.

SCHEDULES (cron en UTC; LATAM = UTC-3 estándar)
- curador: 06:00 hora local diario → 5 contenidos recientes.
- coordinadora: 07:45 hora local L-V → brief diario.
- investigador: jueves 12:00 hora local → papers recientes.
- coordinadora: domingo 18:00 hora local → síntesis semanal.

RESTRICCIONES
- Telegram con un bot único como entrada principal.
- No proponer integraciones que requieran código que aún no existe.`,
  },
  {
    id: "marca-personal",
    title: "Marca personal",
    description:
      "Tres agentes que cuidan la voz pública: arquitecto de marca, escritor de contenidos, analista de mercado.",
    idea:
      "Equipo que cuida la voz pública del usuario en redes profesionales — un agente decide qué es On-brand, otro escribe los posts, otro mide qué resuena.",
    constraints: `USUARIO
- Profesional con marca personal en construcción. Publica regularmente en LinkedIn.
- Voz: clara, sin hype, anclada en investigación y experiencia. Nada de "leverage", "synergy", "unlock potential".
- Cero emojis decorativos.

EQUIPO (3 agentes)

1. brand-architect — define qué es On-brand (opus). Lee los posts publicados y vota qué tono, temas y formatos quedan dentro de la voz. Cierra cada análisis con principios concretos.

2. content-editor — escribe los posts (sonnet). Recibe un ángulo y produce 3 variantes: corta, mediana, larga. Cada una con hook, núcleo y cierre. Sin clickbait.

3. market-analyst — mide qué resuena (haiku). Mira engagement de los últimos 5 posts y articula UNA hipótesis de por qué resonó / no resonó.

LECCIONES INICIALES
- Vocabulario prohibido: leverage, synergy, unlock, game-changer, paradigm shift, disruptive.
- Cero emojis en posts.
- Cero hype: si una afirmación no aguanta una crítica de 30 segundos, no va.
- Si la muestra de datos es chica (<3 posts), decir "no hay señal" en vez de inventar.

SCHEDULES
- brand-architect: lunes 9:00 hora local → revisar posts de la semana, plan editorial.

RESTRICCIONES
- No publicar nada automático: solo borradores, el humano decide.`,
  },
  {
    id: "hija-aprende",
    title: "Mi hija aprende jugando",
    description:
      "Dos agentes que producen mini-juegos web educativos a partir del temario semanal.",
    idea:
      "Convertir el tema de la prueba semanal de mi hija en un mini-juego web jugable que ella abra con doble click y aprenda sin darse cuenta.",
    constraints: `USUARIO
- Madre/padre con hija de 8-11 años. La hija tiene pruebas semanales (biología, historia, matemáticas, etc.).
- La meta no es asistir educativamente: es que la hija aprenda jugando, sin pelear para que se siente.

EQUIPO (2 agentes)

1. game-designer — recibe el tema y elige la mecánica (haiku). Output no es código: es spec clara con pantallas, reglas, colores. Mecánicas posibles: trivia visual, arrastra-y-suelta, memoria, secuencia ordenada.

2. game-coder — toma la spec y genera el archivo (sonnet). Un único HTML autocontenido con CSS+JS embebidos, sin dependencias, sin build. Doble click y juega.

LECCIONES INICIALES
- Nada de leer instrucciones largas: el juego se entiende solo.
- Nada de más de un click por interacción.
- Si la hija no lee fluido, todo con íconos o imágenes (emojis o SVG inline OK).
- Sin librerías externas (sin React, sin Phaser, sin CDN).
- Tiene que correr en Chrome y Edge sin warnings.`,
  },
  {
    id: "investigacion-tema",
    title: "Investigador de un tema nuevo",
    description:
      "Tres agentes que te llevan de cero a sostener una conversación informada en una semana.",
    idea:
      "Cuando necesito dominar un tema nuevo en una semana — investigador recopila fuentes, explainer las traduce a analogías cotidianas, critic cuestiona el consenso.",
    constraints: `USUARIO
- Profesional curioso que necesita aprender un tema nuevo (técnico, científico o social) cada cierto tiempo.
- Lee bien pero no tiene 40 horas: necesita lo esencial bien sintetizado.

EQUIPO (3 agentes)

1. researcher — recopila fuentes (sonnet). 3-5 fuentes seminales (libro/paper/autor) + 3-5 fuentes recientes (últimos 2-3 años). Cita siempre con autor + año + 1 línea de por qué importa.

2. explainer — traduce (sonnet). Toma el dossier del researcher y lo convierte en una versión de 3 minutos para alguien fuera del campo. Usa analogías cotidianas. Marca lo que simplificó.

3. critic — cuestiona (opus). Lee la versión del explainer y articula 2-3 críticas genuinas: qué se omitió, qué consenso podría estar mal, qué evidencia haría falta para cambiar de opinión.

LECCIONES INICIALES
- Nunca inventar DOIs ni datos bibliográficos: si no estás seguro, marcalo como "verificar".
- Priorizar novedad sobre prestigio de revista.
- El critic NO arma strawmen: cada crítica debe ser razonable.

RESTRICCIONES
- Output final como insumo para escritura del usuario, no como Wikipedia.`,
  },
];

const TIPS_IDEA = [
  "Empieza con el outcome real, no con la herramienta.",
  "Una sola línea — el sistema conoce el resto desde los constraints.",
  "Menciona QUÉ debe entregar el equipo, no QUIÉN está en el equipo (eso va abajo).",
  "Si tu primera versión empieza con \"Quiero un asistente con muchas integraciones\", reescríbela: \"Asistente que [outcome concreto]\".",
];

const TIPS_CONSTRAINTS = [
  "USUARIO: quién es, dónde vive, idioma preferido, qué le molesta.",
  "EQUIPO: cuántos agentes, nombres, rol no superpuesto, modelo sugerido (haiku/sonnet/opus por complejidad).",
  "LECCIONES INICIALES: reglas que cada agente lee antes de actuar — idioma, voto explícito, no inventar, qué confirmar antes de actuar externamente.",
  "SCHEDULES SUGERIDOS: cron + tarea, en zona horaria del usuario.",
  "RESTRICCIONES: lo que NO debe proponer el Architect (integraciones que aún no existen, comportamientos no soportados).",
];

const ANTIPATTERNS = [
  {
    bad: "\"Sin Gmail por ahora\" — restricciones temporales en el body del agente",
    why: "Esa frase queda hardcoded en el body del agente. Cuando después conectes Gmail, el modelo sigue creyendo que no lo tiene y no lo usa. Si una integración falta, menciÃ³nalo en RESTRICCIONES (visible al humano), no en el body de los agentes.",
  },
  {
    bad: "Listas de 4000+ caracteres",
    why: "El backend rechaza inputs de más de 4000 chars en CONSTRAINTS. Si tu prompt es muy largo, recortá detalles que el sistema infiere (ej: lista exhaustiva de canales YouTube — eso lo determina el agente al correr, no el Architect).",
  },
  {
    bad: "Detalles de implementación en el prompt",
    why: "No le pidas al Architect que use \"@notionhq/notion-mcp-server\" — eso lo configuras tú después con el MCP Catalog. El Architect propone equipo + roles + reglas, no paquetes npm.",
  },
  {
    bad: "Roles superpuestos entre agentes",
    why: "Si dos agentes hacen \"búsqueda de contenido\", terminan compitiendo o duplicando trabajo. Cada agente tiene UN rol bien recortado: curador (qué leer), investigador (papers), dev (cómo construir). Solapamiento = signo de que un agente sobra.",
  },
  {
    bad: "Mezclar idiomas",
    why: "Si tu prompt dice \"Tone profesional pero relajado, español chileno\" pero la mitad del texto está en inglés, el modelo se confunde. Mantén el prompt entero en el idioma del usuario.",
  },
];

interface Props {
  onCopyExample?: (example: { idea: string; constraints: string }) => void;
}

export function PromptGuide({ onCopyExample }: Props) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<TabId>("idea");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function copyExample(ex: Example) {
    if (onCopyExample) {
      onCopyExample({ idea: ex.idea, constraints: ex.constraints });
    } else {
      // Fallback: copy the whole thing to clipboard.
      const text = `IDEA:\n${ex.idea}\n\nCONSTRAINTS:\n${ex.constraints}`;
      navigator.clipboard?.writeText(text).catch(() => undefined);
    }
    setCopiedId(ex.id);
    setTimeout(() => setCopiedId(null), 1500);
  }

  return (
    <Card className="space-y-3">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 group"
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          <BookOpen size={14} className="text-[--color-accent]" />
          Cómo armar un buen prompt
        </span>
        <ChevronDown
          size={14}
          className={`text-[--color-fg-muted] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="space-y-3 pt-1">
          <div className="flex flex-wrap gap-1 border-b border-[--color-border]">
            <TabButton active={tab === "idea"} onClick={() => setTab("idea")}>
              Idea
            </TabButton>
            <TabButton
              active={tab === "constraints"}
              onClick={() => setTab("constraints")}
            >
              Constraints
            </TabButton>
            <TabButton
              active={tab === "antipatterns"}
              onClick={() => setTab("antipatterns")}
            >
              Anti-patrones
            </TabButton>
            <TabButton active={tab === "examples"} onClick={() => setTab("examples")}>
              Ejemplos
            </TabButton>
          </div>

          {tab === "idea" && (
            <div className="space-y-2 text-[12.5px] leading-relaxed">
              <p className="text-[--color-fg-muted]">
                Una sola línea, orientada al outcome — qué tiene que entregar el equipo, no qué herramientas usa.
              </p>
              <ul className="space-y-1.5 pl-4 list-disc text-[--color-fg]">
                {TIPS_IDEA.map((tip, i) => (
                  <li key={i}>{tip}</li>
                ))}
              </ul>
              <div className="rounded border border-emerald-500/30 bg-emerald-500/5 p-3 text-[11.5px] space-y-1">
                <p className="text-emerald-400 font-medium">Bueno</p>
                <p className="font-mono text-[--color-fg]">
                  "Asistente personal coordinador que orquesta sub-agentes y ayuda a pensar mejor, decidir mejor y escribir mejor."
                </p>
              </div>
              <div className="rounded border border-red-500/30 bg-red-500/5 p-3 text-[11.5px] space-y-1">
                <p className="text-red-400 font-medium">Malo</p>
                <p className="font-mono text-[--color-fg]">
                  "Quiero un asistente con muchas integraciones."
                </p>
              </div>
            </div>
          )}

          {tab === "constraints" && (
            <div className="space-y-2 text-[12.5px] leading-relaxed">
              <p className="text-[--color-fg-muted]">
                El bloque grande donde armas el equipo y sus reglas. Orden recomendado:
              </p>
              <ol className="space-y-1.5 pl-4 list-decimal text-[--color-fg]">
                {TIPS_CONSTRAINTS.map((tip, i) => (
                  <li key={i}>{tip}</li>
                ))}
              </ol>
              <p className="text-[11px] text-[--color-fg-muted] pt-2 border-t border-[--color-border]">
                Tope técnico: 4000 caracteres. Si te pasas, recorta detalles que el agente infiere
                en runtime (lista exhaustiva de canales, autores, herramientas, etc.).
              </p>
            </div>
          )}

          {tab === "antipatterns" && (
            <div className="space-y-2 text-[12.5px]">
              {ANTIPATTERNS.map((ap, i) => (
                <div
                  key={i}
                  className="rounded border border-[--color-border] p-3 space-y-1"
                >
                  <p className="text-red-400 font-medium leading-snug">{ap.bad}</p>
                  <p className="text-[--color-fg-muted] leading-relaxed">{ap.why}</p>
                </div>
              ))}
            </div>
          )}

          {tab === "examples" && (
            <div className="space-y-2 text-[12.5px]">
              <p className="text-[--color-fg-muted] pb-1">
                Cuatro plantillas listas. Click en "Copiar" para autocompletar el formulario.
              </p>
              {EXAMPLES.map((ex) => (
                <div
                  key={ex.id}
                  className="rounded border border-[--color-border] p-3 space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5 min-w-0">
                      <p className="font-medium text-[--color-fg]">{ex.title}</p>
                      <p className="text-[11px] text-[--color-fg-muted]">{ex.description}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyExample(ex)}
                      className="shrink-0 text-[11px]"
                    >
                      {copiedId === ex.id ? (
                        <>
                          <Check size={12} /> Copiado
                        </>
                      ) : (
                        <>
                          <Copy size={12} /> Copiar
                        </>
                      )}
                    </Button>
                  </div>
                  <details className="text-[11px]">
                    <summary className="cursor-pointer text-[--color-fg-muted] hover:text-[--color-fg]">
                      ver el prompt
                    </summary>
                    <div className="mt-2 space-y-2">
                      <div>
                        <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] mb-0.5">
                          Idea
                        </p>
                        <pre className="text-[10.5px] font-mono whitespace-pre-wrap bg-[--color-bg] p-2 rounded">
                          {ex.idea}
                        </pre>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-widest text-[--color-fg-muted] mb-0.5">
                          Constraints
                        </p>
                        <pre className="text-[10.5px] font-mono whitespace-pre-wrap bg-[--color-bg] p-2 rounded max-h-64 overflow-y-auto">
                          {ex.constraints}
                        </pre>
                      </div>
                    </div>
                  </details>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}


function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-[11.5px] px-3 py-1.5 -mb-px transition ${
        active
          ? "text-[--color-fg] border-b-2 border-[--color-accent]"
          : "text-[--color-fg-muted] border-b-2 border-transparent hover:text-[--color-fg]"
      }`}
    >
      {children}
    </button>
  );
}
