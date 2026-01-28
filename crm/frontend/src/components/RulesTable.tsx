/**
 * Rules table component - the heart of the system
 */
import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  Box,
  TextField,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Collapse,
} from '@mui/material';
import { Delete as DeleteIcon, ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import type { Rule } from '../api/rules';
import { rulesApi } from '../api/rules';
import { formatRuleDisplay } from '../utils/urlParser';

interface RulesTableProps {
  profileId: number;
  rules: Rule[];
  onRefresh: () => void;
}

const TYPE_LABELS: Record<string, string> = {
  '*': 'הכל',
  image: 'תמונה',
  video: 'וידאו',
};

const ACTION_LABELS: Record<string, string> = {
  block: 'חסום',
  allow: 'אפשר',
};

export const RulesTable: React.FC<RulesTableProps> = ({ profileId, rules, onRefresh }) => {
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  // Add rule form
  const [newUrl, setNewUrl] = useState('');
  const [newAction, setNewAction] = useState<'block' | 'allow'>('block');
  const [newType, setNewType] = useState<'*' | 'image' | 'video'>('*');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [urlError, setUrlError] = useState<string>('');

  const validateUrl = (url: string): string => {
    if (!url.trim()) return '';
    
    // Remove protocol if present
    let cleanUrl = url.trim();
    if (cleanUrl.startsWith('http://')) {
      cleanUrl = cleanUrl.substring(7);
    } else if (cleanUrl.startsWith('https://')) {
      cleanUrl = cleanUrl.substring(8);
    }
    
    // Check for invalid patterns
    if (cleanUrl.includes('://')) {
      return 'כתובת לא תקינה - הסר את הפרוטוקול';
    }
    
    // Check for multiple slashes in a row (more than 2)
    if (/\/{3,}/.test(cleanUrl)) {
      return 'כתובת לא תקינה - יותר מדי לוכסנים';
    }
    
    // Check for invalid characters
    if (/[<>"|\\\x00-\x1F]/.test(cleanUrl)) {
      return 'כתובת לא תקינה - תווים לא חוקיים';
    }
    
    // Check if starts with *.
    if (cleanUrl.startsWith('*.')) {
      cleanUrl = cleanUrl.substring(2);
    }
    
    // Basic domain validation
    if (cleanUrl.length === 0) {
      return 'כתובת לא תקינה - שדה ריק';
    }
    
    // Check for valid domain pattern
    const parts = cleanUrl.split('/');
    const domain = parts[0];
    
    if (domain.length === 0) {
      return 'כתובת לא תקינה - אין דומיין';
    }
    
    // Domain should contain at least one dot or be localhost
    if (!domain.includes('.') && domain !== 'localhost' && !domain.startsWith('*')) {
      // Allow IP addresses
      const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
      if (!ipPattern.test(domain)) {
        return 'כתובת לא תקינה - דומיין לא תקין';
      }
    }
    
    return '';
  };

  const handleAddRule = async () => {
    if (!newUrl.trim()) return;
    
    const error = validateUrl(newUrl);
    if (error) {
      setUrlError(error);
      return;
    }
    
    try {
      await rulesApi.create(profileId, {
        url: newUrl,
        action: newAction,
        type: newType,
        include_subdomains: includeSubdomains,
      });
      setNewUrl('');
      setIncludeSubdomains(false);
      setNewType('*');
      setNewAction('block');
      setUrlError('');
      onRefresh();
    } catch (error: any) {
      alert(`שגיאה: ${error.message}`);
    }
  };

  const handleDeleteRule = async (id: number) => {
    try {
      await rulesApi.delete(id);
      setDeleteConfirm(null);
      onRefresh();
    } catch (error: any) {
      alert(`שגיאה: ${error.message}`);
    }
  };

  // Handle URL input - check for *. prefix
  const handleUrlChange = (value: string) => {
    setNewUrl(value);
    setUrlError(validateUrl(value));
    if (value.startsWith('*.')) {
      setIncludeSubdomains(true);
    } else if (value.startsWith('*')) {
      setIncludeSubdomains(true);
      setNewUrl(value.substring(1));
    }
  };

  // Handle subdomain checkbox
  const handleSubdomainChange = (checked: boolean) => {
    setIncludeSubdomains(checked);
    if (checked && !newUrl.startsWith('*.')) {
      const parts = newUrl.split('/', 1);
      if (parts[0]) {
        setNewUrl(`*.${parts[0]}${newUrl.includes('/') ? '/' + newUrl.split('/', 2)[1] : ''}`);
      }
    } else if (!checked && newUrl.startsWith('*.')) {
      setNewUrl(newUrl.substring(2));
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleAddRule();
  };

  return (
    <Box>
      {/* Add Rule Form */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <form onSubmit={handleFormSubmit}>
          <Box sx={{ mb: 2 }}>
            <TextField
              fullWidth
              label="כתובת אתר (URL)"
              value={newUrl}
              onChange={(e) => handleUrlChange(e.target.value)}
              placeholder="example.com/path או *.example.com"
              helperText={urlError || "הזן כתובת מלאה. הפרוטוקול (http/https) יוסר אוטומטית"}
              error={!!urlError}
              sx={{ mb: 1 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (!urlError && newUrl.trim()) {
                    handleAddRule();
                  }
                }
              }}
            />
          <FormControlLabel
            control={
              <Checkbox
                checked={includeSubdomains}
                onChange={(e) => handleSubdomainChange(e.target.checked)}
                disabled={newUrl.startsWith('*.')}
              />
            }
            label="כולל סאב-דומיינים"
          />
        </Box>

        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <FormControl sx={{ minWidth: 120 }}>
            <InputLabel>פעולה</InputLabel>
            <Select
              value={newAction}
              onChange={(e) => setNewAction(e.target.value as 'block' | 'allow')}
              label="פעולה"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (!urlError && newUrl.trim()) {
                    handleAddRule();
                  }
                }
              }}
            >
              <MenuItem value="block">חסום</MenuItem>
              <MenuItem value="allow">אפשר</MenuItem>
            </Select>
          </FormControl>

          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={!newUrl.trim() || !!urlError}
          >
            הוסף כלל
          </Button>
        </Box>
        </form>

        {/* Advanced Settings */}
        <Collapse in={showAdvanced}>
          <Box sx={{ mt: 2 }}>
            <FormControl sx={{ minWidth: 120 }}>
              <InputLabel>סוג</InputLabel>
              <Select
                value={newType}
                onChange={(e) => setNewType(e.target.value as '*' | 'image' | 'video')}
                label="סוג"
              >
                <MenuItem value="*">הכל</MenuItem>
                <MenuItem value="image">תמונה</MenuItem>
                <MenuItem value="video">וידאו</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Collapse>

        <Button
          size="small"
          onClick={() => setShowAdvanced(!showAdvanced)}
          endIcon={<ExpandMoreIcon sx={{ transform: showAdvanced ? 'rotate(180deg)' : 'none' }} />}
        >
          הגדרות מתקדמות
        </Button>
      </Paper>

      {/* Rules Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>כתובת</TableCell>
              <TableCell>פעולה</TableCell>
              <TableCell>סוג</TableCell>
              <TableCell align="center">פעולות</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  אין כללים
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell>
                    <code>{formatRuleDisplay(rule)}</code>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={ACTION_LABELS[rule.action]}
                      color={rule.action === 'block' ? 'error' : 'success'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {rule.type !== '*' && (
                      <Chip label={TYPE_LABELS[rule.type]} size="small" variant="outlined" />
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => setDeleteConfirm(rule.id)}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirm !== null} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>מחיקת כלל</DialogTitle>
        <DialogContent>
          האם אתה בטוח שברצונך למחוק את הכלל הזה?
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button
            color="error"
            onClick={() => deleteConfirm !== null && handleDeleteRule(deleteConfirm)}
          >
            מחק
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
