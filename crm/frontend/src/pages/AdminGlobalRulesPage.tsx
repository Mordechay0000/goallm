/**
 * Admin: manage global rules (base whitelist). Admin only.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  TableSortLabel,
  TablePagination,
  InputAdornment,
  Alert,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon, ExpandMore as ExpandMoreIcon, Search as SearchIcon } from '@mui/icons-material';
import { adminApi, type GlobalRule, type GlobalRuleCreate, type GlobalRuleUpdate } from '../api/admin';
import { TagInput } from '../components/TagInput';
import RuleConflictDialog from '../components/RuleConflictDialog';
import { validateDomainOrUrl, processUrlInput, normalizeUrlForRule, WWW_NORMALIZED_MESSAGE } from '../utils/validation';
import { PAGE_DESCRIPTIONS } from '../brand';

const ACTION_LABELS: Record<string, string> = { block: 'חסום', allow: 'אפשר' };

type Order = 'asc' | 'desc';
type OrderBy = 'url' | 'action';
const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

function stableSort<T>(arr: T[], cmp: (a: T, b: T) => number): T[] {
  return [...arr].sort(cmp);
}

function ruleDisplayUrl(r: GlobalRule): string {
  return r.display_url || (r.domain_pattern + (r.path_pattern || ''));
}

const AdminGlobalRulesPage: React.FC = () => {
  const [rules, setRules] = useState<GlobalRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [url, setUrl] = useState('');
  const [action, setAction] = useState<'allow' | 'block'>('allow');
  const [includeSubdomains, setIncludeSubdomains] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [textFilterEnabled, setTextFilterEnabled] = useState(true);
  const [imageFilterEnabled, setImageFilterEnabled] = useState(true);
  const [fileFilterEnabled, setFileFilterEnabled] = useState(true);
  const [pdfFilterEnabled, setPdfFilterEnabled] = useState(true);
  const [videoFilterEnabled, setVideoFilterEnabled] = useState(true);
  const [surfWidgetEnabled, setSurfWidgetEnabled] = useState(true);
  const [urlError, setUrlError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  // Table: search, filter, sort, pagination
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string>('');
  const [order, setOrder] = useState<Order>('asc');
  const [orderBy, setOrderBy] = useState<OrderBy>('url');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  // URL resolve: which rule applies
  const [resolveUrl, setResolveUrl] = useState('');
  const [resolveResult, setResolveResult] = useState<GlobalRule | null | 'loading' | 'invalid'>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [resolveDone, setResolveDone] = useState(false);

  const [editRuleIdError, setEditRuleIdError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  /** When adding a rule: result of check-create (exact match + same-domain rules). Shows conflict/same-domain dialog. */
  const [addRuleCheck, setAddRuleCheck] = useState<{
    exact_match: { rule: GlobalRule; identical: boolean } | null;
    same_domain_rules: GlobalRule[];
    proposed_rule: NonNullable<Awaited<ReturnType<typeof adminApi.checkCreateGlobalRule>>['proposed_rule']>;
    createData: GlobalRuleCreate;
  } | null>(null);

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

  // Open edit dialog when navigating from "בקשות שהתקבלו" with ?edit=ruleId
  useEffect(() => {
    const editId = searchParams.get('edit');
    if (!editId) return;
    const id = parseInt(editId, 10);
    if (Number.isNaN(id)) {
      setSearchParams((p) => {
        const next = new URLSearchParams(p);
        next.delete('edit');
        return next;
      }, { replace: true });
      return;
    }
    setEditRuleIdError(null);
    adminApi
      .getGlobalRule(id)
      .then((rule) => {
        setSearchParams((p) => {
          const next = new URLSearchParams(p);
          next.delete('edit');
          return next;
        }, { replace: true });
        openEdit(rule);
      })
      .catch((e: unknown) => {
        const status = e && typeof e === 'object' && 'response' in e && (e as { response?: { status?: number } }).response?.status;
        setEditRuleIdError(status === 404 ? 'הכלל לא קיים' : 'שגיאה בטעינת הכלל');
        setSearchParams((p) => {
          const next = new URLSearchParams(p);
          next.delete('edit');
          return next;
        }, { replace: true });
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.get('edit')]);

  const openAdd = () => {
    setEditingId(null);
    setUrl('');
    setUrlError('');
    setAction('allow');
    setIncludeSubdomains(false);
    setTags([]);
    setTextFilterEnabled(true);
    setImageFilterEnabled(true);
    setFileFilterEnabled(true);
    setPdfFilterEnabled(true);
    setVideoFilterEnabled(true);
    setSurfWidgetEnabled(true);
    setDialogOpen(true);
  };

  const openEdit = (r: GlobalRule) => {
    setEditingId(r.id);
    const u = r.display_url || (r.domain_pattern + (r.path_pattern || ''));
    setUrl(u);
    setUrlError(validateDomainOrUrl(u));
    setAction((r.action as 'allow' | 'block') || 'allow');
    setIncludeSubdomains(r.include_subdomains || false);
    setTags(r.tags || []);
    setTextFilterEnabled(r.text_filter_enabled !== false);
    setImageFilterEnabled(r.image_filter_enabled !== false);
    setFileFilterEnabled(r.file_filter_enabled !== false);
    setPdfFilterEnabled(r.pdf_filter_enabled !== false);
    setVideoFilterEnabled(r.video_filter_enabled !== false);
    setSurfWidgetEnabled(r.surf_widget_enabled !== false);
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
      const isAllow = action === 'allow';
      const tf = isAllow ? textFilterEnabled : undefined;
      const imgf = isAllow ? imageFilterEnabled : undefined;
      const filef = isAllow ? fileFilterEnabled : undefined;
      const pdff = isAllow ? pdfFilterEnabled : undefined;
      const videof = isAllow ? videoFilterEnabled : undefined;
      const surfw = isAllow ? surfWidgetEnabled : undefined;
      if (editingId) {
        const data: GlobalRuleUpdate = { url: normalized, action, include_subdomains: includeSubdomains, tags: tags.length ? tags : undefined, text_filter_enabled: tf, image_filter_enabled: imgf, file_filter_enabled: filef, pdf_filter_enabled: pdff, video_filter_enabled: videof, surf_widget_enabled: surfw };
        await adminApi.updateGlobalRule(editingId, data);
        setDialogOpen(false);
        setUrlError('');
        await loadRules();
        if (hadWww) alert(WWW_NORMALIZED_MESSAGE);
      } else {
        const data: GlobalRuleCreate = { url: normalized, action, include_subdomains: includeSubdomains, tags: tags.length ? tags : undefined, text_filter_enabled: tf, image_filter_enabled: imgf, file_filter_enabled: filef, pdf_filter_enabled: pdff, video_filter_enabled: videof, surf_widget_enabled: surfw };
        const check = await adminApi.checkCreateGlobalRule(data);
        if (check.exact_match?.identical) {
          alert('כלל זהה כבר קיים ברשימה.');
          setSaving(false);
          return;
        }
        if (check.exact_match || (check.same_domain_rules?.length ?? 0) > 0) {
          setAddRuleCheck({
            exact_match: check.exact_match,
            same_domain_rules: check.same_domain_rules ?? [],
            proposed_rule: check.proposed_rule,
            createData: data,
          });
          setSaving(false);
          return;
        }
        await adminApi.createGlobalRule(data);
        setDialogOpen(false);
        setUrlError('');
        await loadRules();
        if (hadWww) alert(WWW_NORMALIZED_MESSAGE);
      }
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e && (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      alert(msg || 'שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleAddRuleConflictUpdate = async () => {
    if (!addRuleCheck?.exact_match) return;
    setSaving(true);
    try {
      const data: GlobalRuleUpdate = { ...addRuleCheck.createData, url: addRuleCheck.createData.url };
      await adminApi.updateGlobalRule(addRuleCheck.exact_match.rule.id, data);
      setAddRuleCheck(null);
      setDialogOpen(false);
      await loadRules();
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e && (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      alert(msg || 'שגיאה בעדכון');
    } finally {
      setSaving(false);
    }
  };

  const handleAddRuleConflictLeave = () => {
    if ((addRuleCheck?.same_domain_rules?.length ?? 0) > 0) {
      setAddRuleCheck((prev) => prev ? { ...prev, exact_match: null } : null);
    } else {
      setAddRuleCheck(null);
    }
  };

  const handleAddRuleReplace = async (ruleId: number) => {
    if (!addRuleCheck) return;
    setSaving(true);
    try {
      const d = addRuleCheck.createData;
      const data: GlobalRuleUpdate = { action: d.action, include_subdomains: d.include_subdomains, tags: d.tags, text_filter_enabled: d.text_filter_enabled, image_filter_enabled: d.image_filter_enabled, file_filter_enabled: d.file_filter_enabled, pdf_filter_enabled: d.pdf_filter_enabled, video_filter_enabled: d.video_filter_enabled, surf_widget_enabled: d.surf_widget_enabled };
      await adminApi.updateGlobalRule(ruleId, data);
      setAddRuleCheck(null);
      setDialogOpen(false);
      await loadRules();
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e && (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      alert(msg || 'שגיאה בהחלפה');
    } finally {
      setSaving(false);
    }
  };

  const handleAddRuleAnyway = async () => {
    if (!addRuleCheck) return;
    setSaving(true);
    try {
      await adminApi.createGlobalRule(addRuleCheck.createData);
      setAddRuleCheck(null);
      setDialogOpen(false);
      await loadRules();
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e && (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      alert(msg || 'שגיאה בהוספה');
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

  const handleResolveUrl = async () => {
    const u = resolveUrl.trim();
    setResolveError(null);
    if (!u) {
      setResolveResult(null);
      setResolveDone(false);
      return;
    }
    const err = validateDomainOrUrl(u);
    if (err) {
      setResolveResult('invalid');
      setResolveError(err);
      setResolveDone(true);
      return;
    }
    setResolveResult('loading');
    setResolveDone(false);
    try {
      const { rule } = await adminApi.resolveGlobalRule(u);
      setResolveResult(rule);
      setResolveDone(true);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setResolveError(ax?.response?.data?.detail ?? 'שגיאה בבדיקה');
      setResolveResult('invalid');
      setResolveDone(true);
    }
  };

  // Filtered and sorted rules for table
  const filteredRules = (() => {
    let list = rules;
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter((r) => ruleDisplayUrl(r).toLowerCase().includes(q));
    }
    if (filterAction) {
      list = list.filter((r) => (r.action || '') === filterAction);
    }
    return list;
  })();
  const cmp = (a: GlobalRule, b: GlobalRule) => {
    let v = 0;
    if (orderBy === 'url') v = ruleDisplayUrl(a).localeCompare(ruleDisplayUrl(b));
    else v = (a.action || '').localeCompare(b.action || '');
    return order === 'asc' ? v : -v;
  };
  const sortedRules = stableSort(filteredRules, cmp);
  const paginatedRules = sortedRules.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 0 } }} className="page-section container-content">
      {editRuleIdError && (
        <Alert severity="error" onClose={() => setEditRuleIdError(null)} sx={{ mb: 2 }}>
          {editRuleIdError}
        </Alert>
      )}
      <Box className="page-title-section" sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
            רשימת האתרים הגלובלית
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {PAGE_DESCRIPTIONS.adminGlobalRules}
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
          הוסף כלל
        </Button>
      </Box>

      {/* Resolve URL: which rule applies */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box className="card-header-accent" sx={{ mb: 2 }}>
          <Typography variant="h6">בדיקת קישור – איזה כלל גלובלי חל?</Typography>
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
          <TextField
            size="small"
            placeholder="הזן קישור (דומיין או URL מלא)"
            value={resolveUrl}
            onChange={(e) => { setResolveUrl(e.target.value); setResolveResult(null); setResolveError(null); setResolveDone(false); }}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleResolveUrl())}
            sx={{ minWidth: 320 }}
          />
          <Button variant="outlined" size="small" onClick={handleResolveUrl} disabled={!resolveUrl.trim() || resolveResult === 'loading'}>
            {resolveResult === 'loading' ? 'בודק...' : 'בדוק'}
          </Button>
          {resolveResult === 'invalid' && resolveError && (
            <Typography variant="body2" color="error">{resolveError}</Typography>
          )}
          {resolveDone && resolveResult !== 'invalid' && resolveResult !== 'loading' && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              {resolveResult && typeof resolveResult === 'object' ? (
                <>
                  <Typography variant="body2" color="text.secondary">הכלל החל:</Typography>
                  <Chip size="small" label={ruleDisplayUrl(resolveResult)} sx={{ fontFamily: 'monospace' }} />
                  <Chip size="small" variant="outlined" label={ACTION_LABELS[resolveResult.action] ?? resolveResult.action} color={resolveResult.action === 'block' ? 'default' : 'secondary'} />
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">אין כלל גלובלי מתאים לכתובת זו</Typography>
              )}
            </Box>
          )}
        </Box>
      </Paper>

      <Paper>
        <Box className="card-header-accent" sx={{ px: 2, pt: 2, pb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>רשימת כללים גלובליים</Typography>
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
          <TextField
            size="small"
            placeholder="חיפוש (כתובת, דומיין)..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            sx={{ minWidth: 220 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>פעולה</InputLabel>
            <Select value={filterAction} label="פעולה" onChange={(e) => { setFilterAction(e.target.value); setPage(0); }}>
              <MenuItem value="">הכל</MenuItem>
              <MenuItem value="allow">אפשר</MenuItem>
              <MenuItem value="block">חסום</MenuItem>
            </Select>
          </FormControl>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sortDirection={orderBy === 'url' ? order : false}>
                  <TableSortLabel active={orderBy === 'url'} direction={orderBy === 'url' ? order : 'asc'} onClick={() => { setOrderBy('url'); setOrder(orderBy === 'url' && order === 'asc' ? 'desc' : 'asc'); setPage(0); }}>
                    כתובת
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={orderBy === 'action' ? order : false}>
                  <TableSortLabel active={orderBy === 'action'} direction={orderBy === 'action' ? order : 'asc'} onClick={() => { setOrderBy('action'); setOrder(orderBy === 'action' && order === 'asc' ? 'desc' : 'asc'); setPage(0); }}>
                    פעולה
                  </TableSortLabel>
                </TableCell>
                <TableCell>תגיות</TableCell>
                <TableCell>סינון מלל</TableCell>
                <TableCell>סינון תמונות</TableCell>
                <TableCell>סינון קבצים</TableCell>
                <TableCell>סינון PDF</TableCell>
                <TableCell>סינון וידאו/שמע</TableCell>
                <TableCell>וידג'ט</TableCell>
                <TableCell align="left">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={10}>טוען...</TableCell></TableRow>
              ) : filteredRules.length === 0 ? (
                <TableRow><TableCell colSpan={10}>{rules.length === 0 ? 'אין כללים גלובליים' : 'אין תוצאות לחיפוש או לסינון'}</TableCell></TableRow>
              ) : (
                paginatedRules.map((r) => (
                  <TableRow key={r.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                    <TableCell
                      sx={{
                        maxWidth: 400,
                        overflowX: 'auto',
                        whiteSpace: 'nowrap',
                        scrollbarWidth: 'thin',
                        scrollbarColor: '#1e3a5f #e2e8f0',
                        '&::-webkit-scrollbar': { height: 8 },
                        '&::-webkit-scrollbar-track': { background: '#e2e8f0', borderRadius: 8 },
                        '&::-webkit-scrollbar-thumb': { background: '#1e3a5f', borderRadius: 8, border: '2px solid #e2e8f0' },
                        '&::-webkit-scrollbar-thumb:hover': { background: '#152a45' },
                      }}
                    >
                      {ruleDisplayUrl(r)}
                    </TableCell>
                    <TableCell>{ACTION_LABELS[r.action] || r.action}</TableCell>
                    <TableCell>
                      {(r.tags || []).length ? (r.tags || []).map((t) => <Chip key={t} label={t} size="small" sx={{ mr: 0.5 }} />) : '—'}
                    </TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.text_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.image_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.file_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.pdf_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.video_filter_enabled !== false ? 'כן' : 'לא')}</TableCell>
                    <TableCell>{r.action === 'block' ? '—' : (r.surf_widget_enabled !== false ? 'כן' : 'לא')}</TableCell>
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
        {filteredRules.length > 0 && (
          <TablePagination
            component="div"
            count={filteredRules.length}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            rowsPerPageOptions={ROWS_PER_PAGE_OPTIONS}
            labelRowsPerPage="שורות בעמוד:"
            labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count}`}
          />
        )}
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
            helperText={urlError || "פרוטוקול, www. ו־*. יוסרו אוטומטית"}
            sx={{ mt: 1 }}
          />
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>פעולה</InputLabel>
            <Select value={action} label="פעולה" onChange={(e) => setAction(e.target.value as 'allow' | 'block')}>
              <MenuItem value="allow">אפשר</MenuItem>
              <MenuItem value="block">חסום</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel control={<Checkbox checked={includeSubdomains} onChange={(e) => setIncludeSubdomains(e.target.checked)} />} label="כלול תת-דומיינים" sx={{ mt: 2 }} />
          <Box sx={{ mt: 2 }}>
            <TagInput value={tags} onChange={setTags} label="תגיות" helperText="" />
          </Box>
          {action === 'allow' && (
            <Accordion sx={{ mt: 2 }} disableGutters elevation={0} square>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>הגדרות מתקדמות</AccordionSummary>
              <AccordionDetails>
                <FormControlLabel
                  control={<Checkbox checked={textFilterEnabled} onChange={(e) => setTextFilterEnabled(e.target.checked)} />}
                  label="סינון מלל לאתר"
                />
                <FormControlLabel
                  control={<Checkbox checked={imageFilterEnabled} onChange={(e) => setImageFilterEnabled(e.target.checked)} />}
                  label="סינון תמונות לאתר"
                  sx={{ display: 'block', mt: 0.5 }}
                />
                <FormControlLabel
                  control={<Checkbox checked={fileFilterEnabled} onChange={(e) => setFileFilterEnabled(e.target.checked)} />}
                  label="סינון קבצים לאתר"
                  sx={{ display: 'block', mt: 0.5 }}
                />
                <FormControlLabel
                  control={<Checkbox checked={pdfFilterEnabled} onChange={(e) => setPdfFilterEnabled(e.target.checked)} />}
                  label="סינון מסמכים (PDF)"
                  sx={{ display: 'block', mt: 0.5 }}
                />
                <FormControlLabel
                  control={<Checkbox checked={videoFilterEnabled} onChange={(e) => setVideoFilterEnabled(e.target.checked)} />}
                  label="סינון וידאו ושמע (כפתור שלח לבדיקה)"
                  sx={{ display: 'block', mt: 0.5 }}
                />
                <FormControlLabel
                  control={<Checkbox checked={surfWidgetEnabled} onChange={(e) => setSurfWidgetEnabled(e.target.checked)} />}
                  label="הזרקת וידג'ט (סרגל דיווח)"
                  sx={{ display: 'block', mt: 0.5 }}
                />
              </AccordionDetails>
            </Accordion>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>ביטול</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !url.trim() || !!urlError}>{editingId ? 'שמור' : 'הוסף'}</Button>
        </DialogActions>
      </Dialog>

      {/* Add rule: exact match conflict (same domain+path, different content) */}
      {addRuleCheck?.exact_match && (
        <RuleConflictDialog
          open
          onClose={() => setAddRuleCheck(null)}
          data={{
            existing_rule: addRuleCheck.exact_match.rule,
            proposed_rule: addRuleCheck.proposed_rule,
          }}
          approving={saving}
          onUpdate={handleAddRuleConflictUpdate}
          onLeave={handleAddRuleConflictLeave}
        />
      )}

      {/* Add rule: same-domain rules (other rules on domain – add anyway or replace one) */}
      {addRuleCheck && !addRuleCheck.exact_match && (addRuleCheck.same_domain_rules?.length ?? 0) > 0 && (
        <Dialog open onClose={() => setAddRuleCheck(null)} maxWidth="sm" fullWidth>
          <DialogTitle>קיימים כללים על הדומיין</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              קיימים כללים נוספים על אותו דומיין. ניתן להוסיף את הכלל החדש בכל זאת (לא ידרוס כלום) או להחליף אחד מהכללים הקיימים בתוכן החדש.
            </Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>כלל קיים</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="left">פעולה</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {addRuleCheck.same_domain_rules.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{ruleDisplayUrl(r)}</TableCell>
                    <TableCell align="left">
                      <Button size="small" variant="outlined" onClick={() => handleAddRuleReplace(r.id)} disabled={saving}>
                        החלף
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAddRuleCheck(null)} disabled={saving}>ביטול</Button>
            <Button variant="contained" onClick={handleAddRuleAnyway} disabled={saving}>
              {saving ? '...' : 'הוסף בכל זאת'}
            </Button>
          </DialogActions>
        </Dialog>
      )}

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
