"use client";

import { useEffect } from "react";

const DARK_THEME_COLOR = "#010102";
const LIGHT_THEME_COLOR = "#f8f9fb";

/**
 * 把 theme-dark 提升到 <html>。页面根部的 .theme-dark div 只作用于
 * 文档流内的内容；sonner toast / radix dialog / tooltip 等 portal 组件
 * 挂载在 <body> 下，够不到 div 作用域，会以亮色 token 渲染（反色）。
 * 挂到 <html> 后全部 portal 自动继承暗色 token。
 * 同时同步 meta theme-color（浏览器地址栏底色），离开页面时还原亮色。
 */
export function ThemeScope() {
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("theme-dark");
    const meta = document.querySelector('meta[name="theme-color"]');
    const prev = meta?.getAttribute("content") ?? LIGHT_THEME_COLOR;
    meta?.setAttribute("content", DARK_THEME_COLOR);
    return () => {
      root.classList.remove("theme-dark");
      meta?.setAttribute("content", prev);
    };
  }, []);
  return null;
}
