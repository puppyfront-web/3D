"use client";

import { useState } from "react";
import { Loader2, ChevronRight } from "lucide-react";

interface FieldOption {
  label: string;
  value: string;
}

interface MissingField {
  field: string;
  label: string;
  options: FieldOption[];
  current_value?: string;
}

interface ParameterCardBlockProps {
  data: Record<string, unknown>;
  onAction?: (value: string, action: string) => void;
}

export function ParameterCardBlock({ data, onAction }: ParameterCardBlockProps) {
  const missingFields = (Array.isArray(data.missing_fields) ? data.missing_fields : []) as MissingField[];
  const [selectedByField, setSelectedByField] = useState<Record<string, string>>({});

  if (missingFields.length === 0) return null;

  const handleSelect = (fieldName: string, option: FieldOption) => {
    setSelectedByField((prev) => ({ ...prev, [fieldName]: option.value }));
    onAction?.(option.value, fieldName);
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      <div className="divide-y divide-gray-100">
        {missingFields.map((field) => {
          const hasOptions = field.options && field.options.length > 0;
          const selected = selectedByField[field.field];

          return (
            <div key={field.field} className="px-3 py-2.5">
              {/* Field label */}
              <div className="flex items-center gap-1.5 mb-1.5">
                <ChevronRight className="h-3 w-3 text-gray-400" />
                <span className="text-xs font-medium text-gray-600">{field.label}</span>
                {selected && (
                  <span className="text-[10px] text-violet-600 ml-1">已选: {selected}</span>
                )}
              </div>

              {/* Option pills */}
              {hasOptions && (
                <div className="flex flex-wrap gap-1.5 pl-5">
                  {field.options.map((opt, i) => {
                    const isDisabled = !!selected && selected !== opt.value;
                    const isSelected = selected === opt.value;

                    return (
                      <button
                        key={i}
                        onClick={() => handleSelect(field.field, opt)}
                        disabled={!!selected}
                        className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                          isSelected
                            ? "bg-violet-600 text-white scale-95"
                            : isDisabled
                              ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                              : "bg-[#1E3A5F] text-white hover:bg-[#2D5A8E]"
                        }`}
                      >
                        {isSelected && <Loader2 className="h-3 w-3 animate-spin mr-0.5 inline" />}
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* No options hint */}
              {!hasOptions && (
                <p className="text-[11px] text-gray-400 pl-5">请直接在输入框描述</p>
              )}
            </div>
          );
        })}
      </div>

      {/* Hint */}
      <div className="px-3 py-2 bg-gray-50 border-t border-gray-100">
        <p className="text-[10px] text-gray-400">
          选择选项或直接在输入框描述您的需求
        </p>
      </div>
    </div>
  );
}
