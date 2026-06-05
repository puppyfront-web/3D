"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Check } from "lucide-react";

interface WizardStep {
  title: string;
  description: string;
}

interface WizardFormProps {
  steps: WizardStep[];
  children: React.ReactNode;
  currentStep: number;
  onStepChange: (step: number) => void;
  onSubmit: () => void;
  isSubmitting?: boolean;
}

export function WizardForm({
  steps,
  children,
  currentStep,
  onStepChange,
  onSubmit,
  isSubmitting = false,
}: WizardFormProps) {
  const isFirst = currentStep === 0;
  const isLast = currentStep === steps.length - 1;

  return (
    <div className="flex flex-col h-full">
      {/* Step Indicator */}
      <div className="border-b border-gray-200 bg-white px-8 py-5">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          {steps.map((step, index) => (
            <div key={index} className="flex items-center">
              <div className="flex items-center gap-2">
                <div
                  className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium transition-colors ${
                    index < currentStep
                      ? "bg-[#10B981] text-white"
                      : index === currentStep
                      ? "bg-[#1E3A5F] text-white"
                      : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {index < currentStep ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    index + 1
                  )}
                </div>
                <div className="hidden sm:block">
                  <p
                    className={`text-xs font-medium ${
                      index <= currentStep ? "text-[#1A1A2E]" : "text-gray-400"
                    }`}
                  >
                    {step.title}
                  </p>
                  <p className="text-xs text-gray-400">{step.description}</p>
                </div>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`w-16 h-px mx-3 ${
                    index < currentStep ? "bg-[#10B981]" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-6">{children}</div>
      </div>

      {/* Footer */}
      <div className="border-t border-gray-200 bg-white px-8 py-4">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          <Button
            variant="outline"
            onClick={() => onStepChange(currentStep - 1)}
            disabled={isFirst}
            className="gap-1"
          >
            <ChevronLeft className="h-4 w-4" />
            上一步
          </Button>
          <span className="text-xs text-gray-400">
            第 {currentStep + 1} 步，共 {steps.length} 步
          </span>
          {isLast ? (
            <Button
              onClick={onSubmit}
              disabled={isSubmitting}
              className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-1"
            >
              {isSubmitting ? "创建中..." : "创建项目"}
              <Check className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={() => onStepChange(currentStep + 1)}
              className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-1"
            >
              下一步
              <ChevronRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
