import { useState } from "react";
import { useI18n } from "../i18n/I18nProvider";

type StepIndicatorProps = {
  step: number;
  labels: string[];
  onStepChange?: (step: number) => void;
};

export function StepIndicator({ step, labels, onStepChange }: StepIndicatorProps) {
  const { t } = useI18n();
  const [collapsed, setCollapsed] = useState(false);
  const currentStep = step >= 1 && step <= labels.length ? step : 1;

  return (
    <nav className={`step-rail ${collapsed ? "collapsed" : ""}`} aria-label={t("steps")}>
      <button
        type="button"
        className="step-rail-toggle"
        onClick={() => setCollapsed((value) => !value)}
        aria-label={t("toggleSteps")}
        aria-expanded={collapsed ? "false" : "true"}
        title={t("toggleSteps")}
      >
        {/* Circle-and-lines glyph: stacked circles joined by lines (a stepper) */}
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="5" cy="6" r="2.2" />
          <line x1="10" y1="6" x2="20" y2="6" />
          <circle cx="5" cy="12" r="2.2" />
          <line x1="10" y1="12" x2="20" y2="12" />
          <circle cx="5" cy="18" r="2.2" />
          <line x1="10" y1="18" x2="20" y2="18" />
        </svg>
      </button>
       
        <ol className="step-rail-list">
          {labels.map((label, index) => {
            const number = index + 1;
            const active = number === currentStep;
            return (
              <li key={label}>
                <button
                  type="button"
                  className={`step-item ${active ? "active" : ""}`}
                  onClick={() => onStepChange?.(number)}
                  aria-current={active ? "step" : undefined}
                  title={label}
                >
                  <span className="step-pill">{number}</span>
                  {!collapsed && <span className="step-label">{label}</span>}
                </button>
              </li>
            );
          })}
        </ol>
  
    </nav>
  );
}
