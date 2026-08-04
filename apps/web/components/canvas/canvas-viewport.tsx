"use client";

// CanvasViewport — the React Flow canvas surface. Owns the <ReactFlow/> with
// custom ModuleNode, controls (zoom / fit / minimap). Reads nodes/edges from
// the canvas store; persists position changes back.
//
// Board legend colours come from lib/design-tokens.ts (shared with module-node).

import { useCallback } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  type EdgeChange,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useCanvasStore } from "@/lib/canvas-store";
import { ModuleNode } from "./module-node";
import { SectionHeaderNode } from "./section-header-node";

const nodeTypes = { moduleNode: ModuleNode, sectionHeader: SectionHeaderNode };

const DEFAULT_VIEWPORT = { x: 0, y: 0, zoom: 0.75 };

export function CanvasViewport() {
  const rfNodes = useCanvasStore((s) => s.rfNodes);
  const rfEdges = useCanvasStore((s) => s.rfEdges);
  const onNodesChange = useCanvasStore((s) => s.onNodesChange);
  const onEdgesChange = useCanvasStore((s) => s.onEdgesChange);
  const onConnect = useCanvasStore((s) => s.onConnect);
  const isReadOnly = useCanvasStore((s) => s.isReadOnly);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => onNodesChange(changes),
    [onNodesChange],
  );
  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => onEdgesChange(changes),
    [onEdgesChange],
  );

  return (
    <div className="relative w-full h-full">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={onConnect}
        nodesDraggable={!isReadOnly}
        nodesConnectable={!isReadOnly}
        elementsSelectable
        minZoom={0.2}
        maxZoom={1.5}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          className="!bg-surface-container-lowest"
          maskColor="rgba(0, 60, 166, 0.05)"
        />
      </ReactFlow>
    </div>
  );
}
