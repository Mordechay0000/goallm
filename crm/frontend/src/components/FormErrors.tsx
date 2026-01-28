/**
 * Inline form errors display (no browser alerts).
 */
import React from 'react';
import { Alert, AlertTitle, List, ListItem, ListItemText } from '@mui/material';

export interface FormErrorsProps {
  errors: string[];
  title?: string;
  severity?: 'error' | 'warning' | 'info';
}

export const FormErrors: React.FC<FormErrorsProps> = ({
  errors,
  title = 'נא לתקן את השגיאות הבאות',
  severity = 'error',
}) => {
  if (!errors.length) return null;
  return (
    <Alert severity={severity} sx={{ mb: 2 }}>
      <AlertTitle>{title}</AlertTitle>
      <List dense disablePadding sx={{ listStyle: 'disc', pl: 2 }}>
        {errors.map((msg, i) => (
          <ListItem key={i} disablePadding sx={{ display: 'list-item' }}>
            <ListItemText primary={msg} primaryTypographyProps={{ variant: 'body2' }} />
          </ListItem>
        ))}
      </List>
    </Alert>
  );
};
