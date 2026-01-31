/**
 * Unified TagInput component - consistent tag addition UI across the app.
 * Add tags with comma or Enter, remove with backspace or chip delete.
 */
import React from 'react';
import { Box, Chip, TextField, Typography } from '@mui/material';

export interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  label?: string;
  helperText?: string;
  disabled?: boolean;
  size?: 'small' | 'medium';
  /** For compact layouts (e.g. in dialog) */
  compact?: boolean;
}

export const TagInput: React.FC<TagInputProps> = ({
  value,
  onChange,
  placeholder = 'הקלד תגית והקש פסיק או Enter',
  label = 'תגיות',
  helperText = 'תגיות לאתר – משמשות לכללי תגיות',
  disabled = false,
  size = 'small',
  compact = false,
}) => {
  const [input, setInput] = React.useState('');

  const addTag = (v: string) => {
    const trimmed = v.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
      setInput('');
    }
  };

  const removeTag = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === ',' || e.key === 'Enter') {
      e.preventDefault();
      addTag(input);
    } else if (e.key === 'Backspace' && !input && value.length > 0) {
      removeTag(value.length - 1);
    }
  };

  return (
    <Box>
      {(label || helperText) && !compact && (
        <Box sx={{ mb: 0.5 }}>
          <Typography
            component="label"
            variant="body2"
            color="text.secondary"
            sx={{ display: 'block', fontSize: '0.75rem' }}
          >
            {label}
          </Typography>
        </Box>
      )}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 0.5,
          minHeight: compact ? 36 : 40,
          p: compact ? 0.75 : 1,
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
          bgcolor: 'background.paper',
          '&:focus-within': {
            borderColor: 'primary.main',
            borderWidth: 2,
            p: compact ? '3px 5px' : '7px',
          },
        }}
      >
        {value.map((tag, index) => (
          <Chip
            key={`${tag}-${index}`}
            label={tag}
            size="small"
            onDelete={disabled ? undefined : () => removeTag(index)}
            sx={{ mr: 0.25 }}
          />
        ))}
        <TextField
          size={size}
          placeholder={value.length === 0 ? placeholder : 'תגית...'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          sx={{
            flex: 1,
            minWidth: 100,
            '& .MuiInputBase-root': { bgcolor: 'transparent' },
            '& .MuiOutlinedInput-notchedOutline': { border: 'none' },
          }}
          inputProps={{ sx: { py: compact ? 0.25 : 0.5, px: 0.5 } }}
        />
      </Box>
      {helperText && !compact && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
          {helperText}
        </Typography>
      )}
    </Box>
  );
};
