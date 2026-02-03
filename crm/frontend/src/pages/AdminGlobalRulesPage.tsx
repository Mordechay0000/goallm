/**
 * Admin: manage global rules (base whitelist). Admin only.
 */
import React, { useEffect, useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  Button,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon, ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { adminApi, type GlobalRule, type GlobalRuleCreate, type GlobalRuleUpdate } from '../api/admin';
import { TagInput } from '../components/TagInput';
import { validateDomainOrUrl, processUrlInput } from '../utils/validation';

const ACTION_LABELS: Record<string, string> = { block: 'חסום', allow: 'אפשר' };
const TYPE_LABELS: Record<string, string> = { '*': 'הכל', image: 'תמונה', video: 'וידאו' };

const AdminGlobalRulesPage: React.FC = () => {
  const [rules, setRules] = useState<GlobalRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [url, setUrl] = useState('');
  const [action, setAction] = useState<'allow' | 'block'>('allow');
  const [type, setType] = useState('*');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [textFilterEnabled, setTextFilterEnabled] = useState(true);
  const [urlError, setUrlError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const loadRules = async () => {
    setLoading(true);
    try {
      const list = await adminApi.listGlobalRules();
      setRules(list);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  const openAdd = () => {
    setEditingId(null);
    setUrl('');
    setUrlError('');
    setAction('allow');
    setType('*');
    setIncludeSubdomains(false);
    setTags([]);
    setTextFilterEnabled(true);
    setDialogOpen(true);
  };

  const openEdit = (r: GlobalRule) => {
    setEditingId(r.id);
    const u = r.display_url || (r.domain_pattern + (r.path_pattern || ''));
    setUrl(u);
    setUrlError(validateDomainOrUrl(u));
    setAction((r.action as 'allow' | 'block') || 'allow');
    setType(r.type || '*');
    setIncludeSubdomains(r.include_subdomains || false);
    setTags(r.tags || []);
    setTextFilterEnabled(r.text_filter_enabled !== false);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    const u = url.trim();
    const err = validateDomainOrUrl(u);
    if (err) {
      setUrlError(err);
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        const data: GlobalRuleUpdate = { url: u, action, type, include_subdomains: includeSubdomains, tags: tags.length ? tags : undefined, text_filter_enabled: textFilterEnabled };
        await adminApi.updateGlobalRule(editingId, data);
      } else {
        const data: GlobalRuleCreate = { url: u, action, type, include_subdomains: includeSubdomains, tags: tags.length ? tags : undefined, text_filter_enabled: textFilterEnabled };
        await adminApi.createGlobalRule(data);
      }
      setDialogOpen(false);
      setUrlError('');
      await loadRules();
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e && (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      alert(msg || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteGlobalRule(id);
      setDeleteConfirm(null);
      await loadRules();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight={600}>
          רשימה גלובלית
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
          הוסף כלל
        </Button>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        הרשימה הגלובלית היא רשימה לבנה בסיסית – רק כתובות ברשימה זו פתוחות במערכת. משתמשים יכולים להגדיר חסימות נוספות (רשימה שחורה) רק על כתובות שפתוחות ברשימה זו. רק אדמין יכול לערוך את הרשימה הגלובלית.
      </Typography>
      <Paper>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>כתובת</TableCell>
                <TableCell>פעולה</TableCell>
                <TableCell>סוג</TableCell>
                <TableCell>תגיות</TableCell>
                <TableCell>סינון מלל</TableCell>
                <TableCell align="left">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6}>טוען...</TableCell></TableRow>
              ) : rules.length === 0 ? (
                <TableRow><TableCell colSpan={6}>אין כללים גלובליים</TableCell></TableRow>
              ) : (
                rules.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.display_url || (r.domain_pattern + (r.path_pattern || ''))}</TableCell>
                    <TableCell>{ACTION_LABELS[r.action] || r.action}</TableCell>
                    <TableCell>{TYPE_LABELS[r.type] || r.type}</TableCell>
                    <TableCell>
                      {(r.tags || []).length ? (r.tags || []).map((t) => <Chip key={t} label={t} size="small" sx={{ mr: 0.5 }} />) : '—'}
                    </TableCell>
                    <TableCell>{r.text_filter_enabled !== false ? 'כן' : 'לא'}</TableCell>
                    <TableCell align="left">
                      <IconButton size="small" onClick={() => openEdit(r)}><EditIcon /></IconButton>
                      <IconButton size="small" color="error" onClick={() => setDeleteConfirm(r.id)}><DeleteIcon /></IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingId ? 'עריכת כלל גלובלי' : 'הוספת כלל גלובלי'}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="כתובת (דומיין/נתיב)"
            value={url}
            onChange={(e) => {
              const { cleaned, setSubdomains } = processUrlInput(e.target.value);
              setUrl(cleaned);
              setUrlError(validateDomainOrUrl(cleaned));
              if (setSubdomains) setIncludeSubdomains(true);
            }}
            placeholder="example.com או *.example.com/path"
            error={!!urlError}
            helperText={urlError || "פרוטוקול ו־*. יוסרו אוטומטית"}
            sx={{ mt: 1 }}
          />
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>פעולה</InputLabel>
            <Select value={action} label="פעולה" onChange={(e) => setAction(e.target.value as 'allow' | 'block')}>
              <MenuItem value="allow">אפשר</MenuItem>
              <MenuItem value="block">חסום</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>סוג</InputLabel>
            <Select value={type} label="סוג" onChange={(e) => setType(e.target.value)}>
              <MenuItem value="*">הכל</MenuItem>
              <MenuItem value="image">תמונה</MenuItem>
              <MenuItem value="video">וידאו</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel control={<Checkbox checked={includeSubdomains} onChange={(e) => setIncludeSubdomains(e.target.checked)} />} label="כלול תת-דומיינים" sx={{ mt: 2 }} />
          <Box sx={{ mt: 2 }}>
            <TagInput value={tags} onChange={setTags} label="תגיות" helperText="" />
          </Box>
          <Accordion sx={{ mt: 2 }} disableGutters elevation={0} square>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>אפשרויות נוספות</AccordionSummary>
            <AccordionDetails>
              <FormControlLabel
                control={<Checkbox checked={textFilterEnabled} onChange={(e) => setTextFilterEnabled(e.target.checked)} />}
                label="סינון מלל לאתר"
              />
            </AccordionDetails>
          </Accordion>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>ביטול</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !url.trim() || !!urlError}>{editingId ? 'שמור' : 'הוסף'}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteConfirm !== null} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>מחיקת כלל גלובלי</DialogTitle>
        <DialogContent>האם למחוק את הכלל?</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button color="error" variant="contained" onClick={() => deleteConfirm !== null && handleDelete(deleteConfirm)}>מחק</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminGlobalRulesPage;
