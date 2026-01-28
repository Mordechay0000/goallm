/**
 * Password field with show/hide toggle.
 * Use a single asterisk in label for required (e.g. "סיסמה *").
 */
import React, { useState } from 'react';
import { TextField, InputAdornment, IconButton } from '@mui/material';
import { Visibility as VisibilityIcon, VisibilityOff as VisibilityOffIcon } from '@mui/icons-material';

export interface PasswordFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: boolean;
  helperText?: string;
  required?: boolean;
  placeholder?: string;
  disabled?: boolean;
  fullWidth?: boolean;
  sx?: object;
  autoComplete?: string;
  id?: string;
  onBlur?: () => void;
}

export const PasswordField: React.FC<PasswordFieldProps> = ({
  label,
  value,
  onChange,
  error = false,
  helperText,
  required = false,
  placeholder,
  disabled = false,
  fullWidth = true,
  sx,
  autoComplete = 'current-password',
  id,
  onBlur,
}) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <TextField
      id={id}
      fullWidth={fullWidth}
      label={label}
      type={showPassword ? 'text' : 'password'}
      value={value}
      onChange={(e) => onChange(e.target.value as string)}
      onBlur={onBlur}
      error={error}
      helperText={helperText}
      required={required}
      placeholder={placeholder}
      disabled={disabled}
      autoComplete={autoComplete}
      sx={sx}
      inputProps={{ 'data-lpignore': 'true' }}
      InputProps={{
        endAdornment: (
          <InputAdornment position="end">
            <IconButton
              aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'}
              onClick={() => setShowPassword((v) => !v)}
              onMouseDown={(e) => e.preventDefault()}
              edge="end"
              tabIndex={-1}
            >
              {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
};
