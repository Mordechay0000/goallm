/**
 * Label for required fields. Exactly one asterisk (*).
 * Use: <RequiredLabel>שם פרטי</RequiredLabel> -> "שם פרטי *"
 */
import React from 'react';

export interface RequiredLabelProps {
  children: string;
  required?: boolean;
}

export const RequiredLabel: React.FC<RequiredLabelProps> = ({ children, required = true }) => (
  <>{children}{required ? ' *' : ''}</>
);
