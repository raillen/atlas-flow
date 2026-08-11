import type { FC } from "react";
import type { TaskView } from "../api";
import { StatusBadge, card, muted } from "./Primitives";
import { text, tone, toneFor } from "../theme";

/** One task, placed. Coordinates are in the SVG's own units. */
export interface PlacedTask {
  task: TaskView;
  layer: number;
  index: number;
  x: number;
  y: number;
}

export interface Edge {
  from: string;
  to: string;
}

export const NODE_WIDTH = 190;
export const NODE_HEIGHT = 52;
const COLUMN_GAP = 70;
const ROW_GAP = 22;

/**
 * Place layered tasks on a grid: one column per dependency layer.
 *
 * Left to right is the order the scheduler will run them, which is the one
 * thing a reader wants from this picture. Nothing clever is attempted about
 * crossing edges — a plan wide enough for that to matter is a plan whose
 * textual alternative is the better view anyway.
 */
export function placeTasks(layers: TaskView[][]): PlacedTask[] {
  const placed: PlacedTask[] = [];
  layers.forEach((layer, column) => {
    layer.forEach((task, row) => {
      placed.push({
        task,
        layer: column,
        index: row,
        x: column * (NODE_WIDTH + COLUMN_GAP),
        y: row * (NODE_HEIGHT + ROW_GAP),
      });
    });
  });
  return placed;
}

/** Only edges between tasks that are both on screen. */
export function edgesFor(placed: PlacedTask[]): Edge[] {
  const known = new Set(placed.map((item) => item.task.id));
  const edges: Edge[] = [];
  placed.forEach(({ task }) => {
    task.dependencies.forEach((dependency) => {
      if (known.has(dependency)) edges.push({ from: dependency, to: task.id });
    });
  });
  return edges;
}

export function graphSize(placed: PlacedTask[]): { width: number; height: number } {
  if (placed.length === 0) return { width: 0, height: 0 };
  return {
    width: Math.max(...placed.map((item) => item.x)) + NODE_WIDTH,
    height: Math.max(...placed.map((item) => item.y)) + NODE_HEIGHT,
  };
}

/**
 * A sentence describing the plan, for anyone the picture does not serve.
 *
 * Not a fallback for when the SVG fails to load — a peer. A graph that only
 * exists as a drawing is unreadable to a screen reader, and the list below it
 * is the same information rather than a lesser version of it.
 */
export function describeGraph(layers: TaskView[][]): string {
  const total = layers.reduce((sum, layer) => sum + layer.length, 0);
  if (total === 0) return "This plan has no tasks.";
  const shape = layers
    .map((layer, index) => `stage ${index + 1}: ${layer.length}`)
    .join(", ");
  return `${total} task(s) in ${layers.length} stage(s) — ${shape}. Tasks in one stage run together; a later stage waits for the one before it.`;
}

export const TaskGraph: FC<{ layers: TaskView[][] }> = ({ layers }) => {
  const placed = placeTasks(layers);
  const edges = edgesFor(placed);
  const { width, height } = graphSize(placed);
  const byId = new Map(placed.map((item) => [item.task.id, item]));
  const description = describeGraph(layers);

  if (placed.length === 0) {
    return <p style={muted}>{description}</p>;
  }

  return (
    <>
      <p style={muted}>{description}</p>

      {/* Wide plans scroll inside their own box rather than pushing the page. */}
      <div style={{ ...card, overflowX: "auto", padding: "1rem" }}>
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={description}
          style={{ display: "block" }}
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill={tone.neutral.border} />
            </marker>
          </defs>

          {edges.map(({ from, to }) => {
            const start = byId.get(from);
            const end = byId.get(to);
            if (!start || !end) return null;
            const x1 = start.x + NODE_WIDTH;
            const y1 = start.y + NODE_HEIGHT / 2;
            const x2 = end.x;
            const y2 = end.y + NODE_HEIGHT / 2;
            const midpoint = (x1 + x2) / 2;
            return (
              <path
                key={`${from}->${to}`}
                d={`M ${x1} ${y1} C ${midpoint} ${y1}, ${midpoint} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke={tone.neutral.border}
                strokeWidth={1.5}
                markerEnd="url(#arrow)"
              />
            );
          })}

          {placed.map(({ task, x, y }) => {
            const colours = tone[toneFor(task.state)];
            return (
              <g key={task.id}>
                <rect
                  x={x}
                  y={y}
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={8}
                  fill={colours.bg}
                  stroke={colours.border}
                />
                <text
                  x={x + 10}
                  y={y + 20}
                  fontSize="11"
                  fontWeight="600"
                  fill={text.primary}
                >
                  {truncate(task.objective, 26)}
                </text>
                <text x={x + 10} y={y + 38} fontSize="10" fill={colours.fg}>
                  {task.state}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <ol style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0", display: "grid", gap: "0.4rem" }}>
        {layers.map((layer, index) => (
          <li key={index} style={card}>
            <p style={{ ...muted, margin: 0, fontWeight: 600 }}>
              Stage {index + 1}
              {index > 0 && ` · waits for stage ${index}`}
            </p>
            <ul style={{ listStyle: "none", padding: 0, margin: "0.3rem 0 0", display: "grid", gap: "0.25rem" }}>
              {layer.map((task) => (
                <li key={task.id} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <StatusBadge value={task.state} />
                  <span>{task.objective}</span>
                  {task.dependencies.length > 0 && (
                    <span style={muted}>
                      after {task.dependencies.length} task(s)
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </>
  );
};

function truncate(value: string, limit: number): string {
  return value.length <= limit ? value : `${value.slice(0, limit - 1)}…`;
}
