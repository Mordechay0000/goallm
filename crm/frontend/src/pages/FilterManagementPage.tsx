/**
 * Filter Management Page - Main filters management screen
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  Box,
  Button,
  Paper,
  Tabs,
  Tab,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  InputAdornment,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import { useProfilesStore } from '../store/profilesStore';
import { RulesTable } from '../components/RulesTable';
import { rulesApi, tagRulesApi } from '../api/rules';
import type { Rule, TagRule } from '../api/rules';

const FilterManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const { profiles, currentProfile, fetchProfiles, setCurrentProfile } = useProfilesStore();
  const [activeTab, setActiveTab] = useState(0);
  const [rules, setRules] = useState<Rule[]>([]);
  const [tagRules, setTagRules] = useState<TagRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewProfile, setShowNewProfile] = useState(false);
  const [newProfileName, setNewProfileName] = useState('');
  const [newProfileMode, setNewProfileMode] = useState<'whitelist' | 'blacklist'>('whitelist');
  const [newTagRuleTag, setNewTagRuleTag] = useState('');
  const [newTagRuleState, setNewTagRuleState] = useState<'allow' | 'block'>('block');
  const [tagRuleDeleteConfirm, setTagRuleDeleteConfirm] = useState<number | null>(null);
  const [tagOrder, setTagOrder] = useState<'asc' | 'desc'>('asc');
  const [tagOrderBy, setTagOrderBy] = useState<'tag' | 'state'>('tag');
  const [tagPage, setTagPage] = useState(0);
  const [tagRowsPerPage, setTagRowsPerPage] = useState(10);
  const [tagSearch, setTagSearch] = useState('');
  const TAG_ROWS_OPTIONS = [10, 25, 50];

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  useEffect(() => {
    if (profiles.length > 0) {
      const currentIndex = profiles.findIndex(p => p.id === currentProfile?.id);
      setActiveTab(currentIndex >= 0 ? currentIndex : 0);
      loadRules();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- loadRules when profile tab changes
  }, [profiles, currentProfile]);

  const loadRules = async () => {
    if (!currentProfile) return;
    setLoading(true);
    try {
      const [rulesData, tagRulesData] = await Promise.all([
        rulesApi.list(currentProfile.id),
        tagRulesApi.list(),
      ]);
      setRules(rulesData);
      setTagRules(tagRulesData);
    } catch (error: unknown) {
      console.error('Error loading rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddTagRule = async () => {
    if (!newTagRuleTag.trim()) return;
    try {
      await tagRulesApi.create({ tag: newTagRuleTag.trim(), state: newTagRuleState });
      setNewTagRuleTag('');
      setNewTagRuleState('block');
      await loadRules();
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleDeleteTagRule = async (id: number) => {
    try {
      await tagRulesApi.delete(id);
      setTagRuleDeleteConfirm(null);
      await loadRules();
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
    if (profiles[newValue]) {
      setCurrentProfile(profiles[newValue]);
    }
  };

  const handleCreateProfile = async () => {
    if (!newProfileName.trim()) return;
    try {
      await useProfilesStore.getState().createProfile(newProfileName, newProfileMode);
      setNewProfileName('');
      setShowNewProfile(false);
      await fetchProfiles();
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const selectedProfile = profiles[activeTab];

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <IconButton onClick={() => navigate('/')} color="secondary" sx={{ mb: 1, mr: 1 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          ניהול פילטרים
        </Typography>
        <Typography variant="body2" color="text.secondary">
          הוסף, ערוך ומחק אתרים (חסום/פתוח) לכל פרופיל
        </Typography>
      </Box>

      {/* Profile Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            variant="scrollable"
            scrollButtons="auto"
          >
            {profiles.map((profile) => (
              <Tab
                key={profile.id}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <span>{profile.name}</span>
                    {profile.is_default && (
                      <Chip label="ברירת מחדל" size="small" color="secondary" />
                    )}
                  </Box>
                }
              />
            ))}
            <Tab
              icon={<AddIcon />}
              onClick={() => setShowNewProfile(true)}
            />
          </Tabs>
        </Box>

        {/* Profile Info */}
        {selectedProfile && (
          <Box sx={{ p: 3 }}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                {selectedProfile.name}
              </Typography>
              <Chip
                label={selectedProfile.mode === 'whitelist' ? 'הכל חסום – אוסיף פתיחות' : 'הכל פתוח – אוסיף חסימות'}
                color={selectedProfile.mode === 'whitelist' ? 'default' : 'secondary'}
                variant="outlined"
                sx={{ mb: 2 }}
              />
              <Typography variant="body2" color="text.secondary" paragraph>
                {selectedProfile.mode === 'whitelist' ? (
                  <>כל האתרים חסומים – תוסיף רק את האתרים שתרצה לפתוח.</>
                ) : (
                  <>כל האתרים פתוחים – תוסיף רק את האתרים שתרצה לחסום.</>
                )}
              </Typography>
            </Box>
          </Box>
        )}
      </Paper>

      {/* Rules Table */}
      {selectedProfile && !loading && (
        <RulesTable
          profileId={selectedProfile.id}
          rules={rules}
          onRefresh={loadRules}
        />
      )}

      {/* Tag Rules (כללי תגיות) */}
      <Paper sx={{ p: 2, mt: 3 }}>
        <Box className="card-header-accent" sx={{ mb: 2 }}>
          <Typography variant="h6">
            כללי תגיות
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          חסימה או פתיחה לפי תגית – למשל: אתרים עם תגית &quot;ממכר&quot; חסומים. התגיות מוגדרות לכל אתר בטבלה למעלה.
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
          <TextField
            size="small"
            placeholder="חיפוש תגיות..."
            value={tagSearch}
            onChange={(e) => { setTagSearch(e.target.value); setTagPage(0); }}
            sx={{ minWidth: 200 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
          <TextField
            size="small"
            label="תגית"
            value={newTagRuleTag}
            onChange={(e) => setNewTagRuleTag(e.target.value)}
            placeholder="ממכר"
            sx={{ minWidth: 140 }}
          />
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>פעולה</InputLabel>
            <Select
              value={newTagRuleState}
              onChange={(e) => setNewTagRuleState(e.target.value as 'allow' | 'block')}
              label="פעולה"
            >
              <MenuItem value="block">חסום</MenuItem>
              <MenuItem value="allow">אפשר</MenuItem>
            </Select>
          </FormControl>
          <Button variant="contained" onClick={handleAddTagRule} disabled={!newTagRuleTag.trim()}>
            הוסף כלל תגית
          </Button>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sortDirection={tagOrderBy === 'tag' ? tagOrder : false}>
                  <TableSortLabel active={tagOrderBy === 'tag'} direction={tagOrderBy === 'tag' ? tagOrder : 'asc'} onClick={() => { setTagOrderBy('tag'); setTagOrder(tagOrderBy === 'tag' && tagOrder === 'asc' ? 'desc' : 'asc'); setTagPage(0); }}>
                    תגית
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={tagOrderBy === 'state' ? tagOrder : false}>
                  <TableSortLabel active={tagOrderBy === 'state'} direction={tagOrderBy === 'state' ? tagOrder : 'asc'} onClick={() => { setTagOrderBy('state'); setTagOrder(tagOrderBy === 'state' && tagOrder === 'asc' ? 'desc' : 'asc'); setTagPage(0); }}>
                    פעולה
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(() => {
                const q = tagSearch.trim().toLowerCase();
                const filtered = !q
                  ? tagRules
                  : tagRules.filter((tr) => (tr.tag || '').toLowerCase().includes(q) || (tr.state || '').toLowerCase().includes(q));
                if (filtered.length === 0) {
                  return (
                    <TableRow>
                      <TableCell colSpan={3} align="center">
                        {tagRules.length === 0 ? 'אין כללי תגיות' : 'אין תוצאות לחיפוש'}
                      </TableCell>
                    </TableRow>
                  );
                }
                const sorted = [...filtered].sort((a, b) => {
                  let v = 0;
                  if (tagOrderBy === 'tag') v = (a.tag || '').localeCompare(b.tag || '');
                  else v = (a.state || '').localeCompare(b.state || '');
                  return tagOrder === 'asc' ? v : -v;
                });
                const paginated = sorted.slice(tagPage * tagRowsPerPage, tagPage * tagRowsPerPage + tagRowsPerPage);
                return paginated.map((tr) => (
                    <TableRow key={tr.id} hover sx={{ '&:hover': { bgcolor: 'action.selected' } }}>
                      <TableCell>{tr.tag}</TableCell>
                      <TableCell>
                        <Chip
                          label={tr.state === 'block' ? 'חסום' : 'אפשר'}
                          color={tr.state === 'block' ? 'default' : 'secondary'}
                          variant="outlined"
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="center">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => setTagRuleDeleteConfirm(tr.id)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                ));
              })()}
            </TableBody>
          </Table>
          {(() => {
            const q = tagSearch.trim().toLowerCase();
            const filtered = !q ? tagRules : tagRules.filter((tr) => (tr.tag || '').toLowerCase().includes(q) || (tr.state || '').toLowerCase().includes(q));
            const n = filtered.length;
            return n > 0 ? (
              <TablePagination
                component="div"
                count={n}
                page={tagPage}
                onPageChange={(_, p) => setTagPage(p)}
                rowsPerPage={tagRowsPerPage}
                onRowsPerPageChange={(e) => { setTagRowsPerPage(parseInt(e.target.value, 10)); setTagPage(0); }}
                rowsPerPageOptions={TAG_ROWS_OPTIONS}
                labelRowsPerPage="שורות בעמוד:"
                labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count}`}
              />
            ) : null;
          })()}
        </TableContainer>
      </Paper>

      {/* Tag Rule Delete Confirmation */}
      <Dialog open={tagRuleDeleteConfirm !== null} onClose={() => setTagRuleDeleteConfirm(null)}>
        <DialogTitle>מחיקת כלל תגית</DialogTitle>
        <DialogContent>האם למחוק את כלל התגית?</DialogContent>
        <DialogActions>
          <Button onClick={() => setTagRuleDeleteConfirm(null)}>ביטול</Button>
          <Button
            color="error"
            onClick={() => tagRuleDeleteConfirm !== null && handleDeleteTagRule(tagRuleDeleteConfirm)}
          >
            מחק
          </Button>
        </DialogActions>
      </Dialog>

      {/* New Profile Dialog */}
      <Dialog open={showNewProfile} onClose={() => setShowNewProfile(false)} maxWidth="sm" fullWidth>
        <DialogTitle>פרופיל חדש</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="שם פרופיל"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            sx={{ mb: 2, mt: 1 }}
          />
          <FormControl fullWidth>
            <InputLabel>מצב עבודה</InputLabel>
            <Select
              value={newProfileMode}
              onChange={(e) => setNewProfileMode(e.target.value as 'whitelist' | 'blacklist')}
              label="מצב עבודה"
            >
              <MenuItem value="whitelist">הכל חסום – אוסיף פתיחות</MenuItem>
              <MenuItem value="blacklist">הכל פתוח – אוסיף חסימות</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowNewProfile(false)}>ביטול</Button>
          <Button variant="contained" onClick={handleCreateProfile}>
            צור
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default FilterManagementPage;
