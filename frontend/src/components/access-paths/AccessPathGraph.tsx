import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
  Position,
  Handle,
} from "@xyflow/react";
import dagre from "dagre";
import "@xyflow/react/dist/style.css";
import type { AccessPath, AccessPathNodeType } from "@/api/types";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 48;

const NODE_COLORS: Record<AccessPathNodeType, { bg: string; border: string; text: string }> = {
  user: { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af" },
  service_principal: { bg: "#f5f3ff", border: "#8b5cf6", text: "#5b21b6" },
  application: { bg: "#ecfdf5", border: "#10b981", text: "#065f46" },
  group: { bg: "#fffbeb", border: "#f59e0b", text: "#92400e" },
  directory_role: { bg: "#fef2f2", border: "#ef4444", text: "#991b1b" },
  app_permission: { bg: "#fef2f2", border: "#ef4444", text: "#991b1b" },
};

const NODE_ICONS: Record<AccessPathNodeType, string> = {
  user: "\u{1F464}",
  service_principal: "⚙️",
  application: "\u{1F4E6}",
  group: "\u{1F465}",
  directory_role: "\u{1F6E1}️",
  app_permission: "\u{1F511}",
};

function PathNode({ data }: { data: { label: string; nodeType: AccessPathNodeType } }) {
  const colors = NODE_COLORS[data.nodeType] ?? NODE_COLORS.user;
  const icon = NODE_ICONS[data.nodeType] ?? "";

  return (
    <>
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <div
        className="flex items-center gap-2 rounded-lg border-2 px-3 py-2 text-xs font-medium shadow-sm"
        style={{
          background: colors.bg,
          borderColor: colors.border,
          color: colors.text,
          minWidth: NODE_WIDTH,
          maxWidth: NODE_WIDTH,
        }}
      >
        <span className="text-sm">{icon}</span>
        <span className="truncate">{data.label}</span>
      </div>
      <Handle type="source" position={Position.Right} className="opacity-0" />
    </>
  );
}

const nodeTypes: NodeTypes = {
  pathNode: PathNode,
};

function layoutGraph(nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 80 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });

  return { nodes: layoutedNodes, edges };
}

function pathsToGraph(paths: AccessPath[]): { nodes: Node[]; edges: Edge[] } {
  const nodeMap = new Map<string, Node>();
  const edgeSet = new Set<string>();
  const edges: Edge[] = [];

  const RISK_EDGE_COLORS: Record<string, string> = {
    critical: "#ef4444",
    high: "#f97316",
    medium: "#f59e0b",
  };

  for (const path of paths) {
    const edgeColor = RISK_EDGE_COLORS[path.risk_level] ?? "#94a3b8";

    for (let i = 0; i < path.steps.length; i++) {
      const step = path.steps[i];
      const nodeId = `${step.node.node_type}_${step.node.id}`;

      if (!nodeMap.has(nodeId)) {
        nodeMap.set(nodeId, {
          id: nodeId,
          type: "pathNode",
          data: { label: step.node.display_name, nodeType: step.node.node_type },
          position: { x: 0, y: 0 },
        });
      }

      if (i > 0 && step.edge) {
        const prevStep = path.steps[i - 1];
        const sourceId = `${prevStep.node.node_type}_${prevStep.node.id}`;
        const edgeId = `${sourceId}->${nodeId}`;

        if (!edgeSet.has(edgeId)) {
          edgeSet.add(edgeId);
          edges.push({
            id: edgeId,
            source: sourceId,
            target: nodeId,
            label: step.edge.description,
            animated: path.risk_level === "critical",
            style: { stroke: edgeColor, strokeWidth: 2 },
            labelStyle: { fontSize: 10, fill: "#64748b" },
            labelBgStyle: { fill: "#ffffff", fillOpacity: 0.9 },
          });
        }
      }
    }
  }

  const nodes = Array.from(nodeMap.values());
  return layoutGraph(nodes, edges);
}

interface AccessPathGraphProps {
  paths: AccessPath[];
  height?: number;
}

export function AccessPathGraph({ paths, height = 400 }: AccessPathGraphProps) {
  const { nodes, edges } = useMemo(() => pathsToGraph(paths), [paths]);

  const onInit = useCallback((instance: { fitView: () => void }) => {
    setTimeout(() => instance.fitView(), 50);
  }, []);

  if (paths.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-sm text-slate-400 dark:text-slate-500"
        style={{ height }}
      >
        No privilege escalation paths detected
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onInit={onInit}
        fitView
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeStrokeWidth={2}
          nodeColor={(n) => {
            const nt = (n.data as { nodeType?: AccessPathNodeType }).nodeType;
            return nt ? NODE_COLORS[nt]?.border ?? "#94a3b8" : "#94a3b8";
          }}
          style={{ height: 80, width: 120 }}
        />
      </ReactFlow>
    </div>
  );
}
