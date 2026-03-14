/**
 * Admin: manage site injections (head/body code + hide selectors per site). Admin only.
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
  FormControlLabel,
  Checkbox,
  Chip,
  Switch,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon } from '@mui/icons-material';
import { adminApi, type SiteInjection, type SiteInjectionCreate, type SiteInjectionUpdate } from '../api/admin';
import { validateDomainOrUrl, processUrlInput, normalizeUrlForRule, WWW_NORMALIZED_MESSAGE } from '../utils/validation';
import { PAGE_DESCRIPTIONS } from '../brand';

function ruleDisplayUrl(r: SiteInjection): string {
  const domain = r.domain_pattern || '';
  const path = r.path_pattern || '';
  const prefix = r.include_subdomains && !domain.startsWith('*.') ? '*.' : '';
  return prefix + domain + (path && path !== '/' ? path : '');
}

const AdminSiteInjectionsPage: React.FC = () => {
  const [rules, setRules] = useState<SiteInjection[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [url, setUrl] = useState('');
  const [urlError, setUrlError] = useState('');
  const [headCode, setHeadCode] = useState('');
  const [bodyCode, setBodyCode] = useState('');
  const [hideSelectorsText, setHideSelectorsText] = useState('');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [pathExactOnly, setPathExactOnly] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const loadRules = async () => {
    setLoading(true);
    try {
      const list = await adminApi.listSiteInjections();
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
    setHeadCode('');
    setBodyCode('');
    setHideSelectorsText('');
    setIncludeSubdomains(false);
    setPathExactOnly(true);
    setEnabled(true);
    setDialogOpen(true);
  };

  const openEdit = (r: SiteInjection) => {
    setEditingId(r.id);
    setUrl(ruleDisplayUrl(r));
    setUrlError(validateDomainOrUrl(ruleDisplayUrl(r)));
    setHeadCode(r.head_code || '');
    setBodyCode(r.body_code || '');
    setHideSelectorsText((r.hide_selectors_list || []).join('\n'));
    setIncludeSubdomains(r.include_subdomains || false);
    setPathExactOnly(r.path_exact_only !== false);
    setEnabled(r.enabled !== false);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    const { normalized, hadWww } = normalizeUrlForRule(url.trim());
    const err = validateDomainOrUrl(normalized);
    if (err) {
      setUrlError(err);
      return;
    }
    setSaving(true);
    try {
      const hideList = hideSelectorsText
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);
      if (editingId) {
        const data: SiteInjectionUpdate = {
          url: normalized,
          head_code: headCode.trim() || undefined,
          body_code: bodyCode.trim() || undefined,
          hide_selectors: hideList.length ? hideList : undefined,
          include_subdomains: includeSubdomains,
          path_exact_only: pathExactOnly,
          enabled,
        };
        await adminApi.updateSiteInjection(editingId, data);
        setDialogOpen(false);
        setUrlError('');
        await loadRules();
        if (hadWww) alert(WWW_NORMALIZED_MESSAGE);
      } else {
        const data: SiteInjectionCreate = {
          url: normalized,
          head_code: headCode.trim() || undefined,
          body_code: bodyCode.trim() || undefined,
          hide_selectors: hideList.length ? hideList : undefined,
          include_subdomains: includeSubdomains,
          path_exact_only: pathExactOnly,
          enabled,
        };
        await adminApi.createSiteInjection(data);
        setDialogOpen(false);
        setUrlError('');
        await loadRules();
        if (hadWww) alert(WWW_NORMALIZED_MESSAGE);
      }
    } catch (e: unknown) {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      alert(msg || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteSiteInjection(id);
      setDeleteConfirm(null);
      await loadRules();
    } catch (e) {
      console.error(e);
    }
  };

  const truncate = (s: string, len: number) =>
    !s ? '' : s.length <= len ? s : s.slice(0, len) + '…';

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 0 } }} className="page-section container-content">
      <Box className="page-title-section" sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
            הזרקות לאתר
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {PAGE_DESCRIPTIONS.adminSiteInjections}
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
          הוסף כלל הזרקה
        </Button>
      </Box>

      <Paper>
        <Box className="card-header-accent" sx={{ px: 2, pt: 2, pb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            רשימת הזרקות
          </Typography>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>כתובת</TableCell>
                <TableCell>התאמה</TableCell>
                <TableCell>קוד ב־head</TableCell>
                <TableCell>קוד ב־body</TableCell>
                <TableCell>הסתרת רכיבים</TableCell>
                <TableCell>פעיל</TableCell>
                <TableCell align="left">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7}>טוען...</TableCell>
                </TableRow>
              ) : rules.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7}>אין כללי הזרקה. הוסף כלל כדי להזריק קוד או להסתיר רכיבים באתר.</TableCell>
                </TableRow>
              ) : (
                rules.map((r) => (
                  <TableRow key={r.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                    <TableCell sx={{ fontFamily: 'monospace', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {ruleDisplayUrl(r)}
                    </TableCell>
                    <TableCell>
                      {r.path_exact_only !== false ? 'רק הכתובת' : 'כתובת + נתיבים מתחת'}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {r.head_code ? truncate(r.head_code, 40) : '—'}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {r.body_code ? truncate(r.body_code, 40) : '—'}
                    </TableCell>
                    <TableCell>
                      {(r.hide_selectors_list || []).length
                        ? (r.hide_selectors_list || []).map((sel) => (
                            <Chip key={sel} label={truncate(sel, 25)} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                          ))
                        : '—'}
                    </TableCell>
                    <TableCell>{r.enabled !== false ? 'כן' : 'לא'}</TableCell>
                    <TableCell align="left">
                      <IconButton size="small" onClick={() => openEdit(r)}>
                        <EditIcon />
                      </IconButton>
                      <IconButton size="small" color="error" onClick={() => setDeleteConfirm(r.id)}>
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingId ? 'עריכת כלל הזרקה' : 'הוספת כלל הזרקה'}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="כתובת אתר (דומיין או דומיין/נתיב)"
            value={url}
            onChange={(e) => {
              const { cleaned, setSubdomains } = processUrlInput(e.target.value);
              setUrl(cleaned);
              setUrlError(validateDomainOrUrl(cleaned));
              if (setSubdomains) setIncludeSubdomains(true);
            }}
            placeholder="example.com או *.example.com/path"
            error={!!urlError}
            helperText={urlError || 'פרוטוקול ו־www יוסרו אוטומטית'}
            sx={{ mt: 1 }}
          />
          <FormControlLabel
            control={<Checkbox checked={includeSubdomains} onChange={(e) => setIncludeSubdomains(e.target.checked)} />}
            label="כלול תת־דומיינים"
            sx={{ mt: 2 }}
          />
          <FormControlLabel
            control={<Checkbox checked={pathExactOnly} onChange={(e) => setPathExactOnly(e.target.checked)} />}
            label="החל רק על הכתובת הזו (לא על נתיבים מתחת)"
            sx={{ mt: 1, display: 'block' }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            אם לא מסומן – ההזרקה תחול גם על כל הנתיבים תחת הנתיב (כמו בכללים).
          </Typography>
          <TextField
            fullWidth
            label="קוד להזרקה ל־&lt;head&gt;"
            value={headCode}
            onChange={(e) => setHeadCode(e.target.value)}
            placeholder="<style>...</style> או <script>...</script>"
            multiline
            minRows={2}
            sx={{ mt: 2 }}
          />
          <TextField
            fullWidth
            label="קוד להזרקה לפני &lt;/body&gt;"
            value={bodyCode}
            onChange={(e) => setBodyCode(e.target.value)}
            placeholder="HTML או סקריפט"
            multiline
            minRows={2}
            sx={{ mt: 2 }}
          />
          <TextField
            fullWidth
            label="בוררים להסתרה (שורה אחת לכל בורר CSS)"
            value={hideSelectorsText}
            onChange={(e) => setHideSelectorsText(e.target.value)}
            placeholder={'.ad, #sidebar, [data-banner]'}
            multiline
            minRows={2}
            helperText="למשל: .ad, #sidebar, [data-banner]"
            sx={{ mt: 2 }}
          />
          <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
            label="פעיל"
            sx={{ mt: 2, display: 'block' }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>ביטול</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !url.trim() || !!urlError}>
            {editingId ? 'שמור' : 'הוסף'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteConfirm !== null} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>מחיקת כלל הזרקה</DialogTitle>
        <DialogContent>האם למחוק את כלל ההזרקה?</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>ביטול</Button>
          <Button color="error" variant="contained" onClick={() => deleteConfirm !== null && handleDelete(deleteConfirm)}>
            מחק
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminSiteInjectionsPage;
