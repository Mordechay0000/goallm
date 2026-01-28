/**
 * Stepper Component - For wizard-style workflows
 * Minimal, functional design
 */
import React from 'react';
import {
  Stepper as MuiStepper,
  Step,
  StepLabel,
  StepContent,
  Box,
  Typography,
  Button,
  Paper,
} from '@mui/material';

interface StepData {
  label: string;
  description?: string;
  content: React.ReactNode;
  optional?: boolean;
}

interface StepperProps {
  steps: StepData[];
  activeStep: number;
  onNext: () => void;
  onBack: () => void;
  onFinish?: () => void;
  nextLabel?: string;
  backLabel?: string;
  finishLabel?: string;
  orientation?: 'horizontal' | 'vertical';
  showActions?: boolean;
}

export const Stepper: React.FC<StepperProps> = ({
  steps,
  activeStep,
  onNext,
  onBack,
  onFinish,
  nextLabel = 'הבא',
  backLabel = 'חזור',
  finishLabel = 'סיום',
  orientation = 'horizontal',
  showActions = true,
}) => {
  const isLastStep = activeStep === steps.length - 1;
  const isFirstStep = activeStep === 0;

  return (
    <Box>
      <MuiStepper activeStep={activeStep} orientation={orientation} sx={{ mb: 4 }}>
        {steps.map((step, index) => (
          <Step key={step.label} completed={index < activeStep}>
            <StepLabel
              optional={
                step.optional ? (
                  <Typography variant="caption">אופציונלי</Typography>
                ) : undefined
              }
            >
              {step.label}
            </StepLabel>
            {orientation === 'vertical' && (
              <StepContent>
                {index === activeStep && (
                  <Box sx={{ mt: 2 }}>
                    {step.description && (
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {step.description}
                      </Typography>
                    )}
                    {step.content}
                  </Box>
                )}
              </StepContent>
            )}
          </Step>
        ))}
      </MuiStepper>

      {orientation === 'horizontal' && (
        <Paper sx={{ p: 3, mb: 3 }}>
          {steps[activeStep].description && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {steps[activeStep].description}
            </Typography>
          )}
          {steps[activeStep].content}
        </Paper>
      )}

      {showActions && (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
          <Button
            disabled={isFirstStep}
            onClick={onBack}
            variant="outlined"
          >
            {backLabel}
          </Button>
          <Button
            variant="contained"
            onClick={isLastStep ? onFinish : onNext}
          >
            {isLastStep ? finishLabel : nextLabel}
          </Button>
        </Box>
      )}
    </Box>
  );
};

export default Stepper;
