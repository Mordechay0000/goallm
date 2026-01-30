/**
 * Schedules page - manage all schedules from all profiles
 * Minimal admin design
 */
import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Button,
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
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
  TableSortLabel,
  TablePagination,
  InputAdornment,
} from '@mui/material';
import { Delete as DeleteIcon, Add as AddIcon, Search as SearchIcon } from '@mui/icons-material';
import { schedulesApi } from '../api/schedules';
import { profilesApi } from '../api/profiles';
import { useProfilesStore } from '../store/profilesStore';
import type { Schedule } from '../api/schedules';

const DAYS_HEBREW = ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ש'];

interface ScheduleWithProfile extends Schedule {
  profile_name?: string;
}

const SchedulesPage: React.FC = () => {
  const location = useLocation();
  const { profiles, fetchProfiles } = useProfilesStore();
  const [schedules, setSchedules] = useState<ScheduleWithProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [selectedProfileId, setSelectedProfileId] = useState<number | ''>('');
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [useHours, setUseHours] = useState(false);
  const [fromTime, setFromTime] = useState('18:00');
  const [toTime, setToTime] = useState('22:00');
  const [schedOrder, setSchedOrder] = useState<'asc' | 'desc'>('asc');
  const [schedOrderBy, setSchedOrderBy] = useState<'profile' | 'from' | 'to'>('profile');
  const [schedPage, setSchedPage] = useState(0);
  const [schedRowsPerPage, setSchedRowsPerPage] = useState(10);
  const [schedSearch, setSchedSearch] = useState('');
  const SCHED_ROWS_OPTIONS = [10, 25, 50];

  // Check if we should open dialog from location state
  useEffect(() => {
    const state = location.state as { openDialog?: boolean; profileId?: number } | null;
    if (state?.openDialog && state?.profileId) {
      const openDialogWithProfile = async () => {
        // Make sure profiles are loaded first
        if (profiles.length === 0) {
          await fetchProfiles();
        }
        setSelectedProfileId(state.profileId!);
        setShowAddDialog(true);
      };
      openDialogWithProfile();
      // Clear state
      window.history.replaceState({}, document.title);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location]);

  const fetchAllSchedules = async () => {
    setLoading(true);
    try {
      // Fetch profiles first
      let profilesList = profiles;
      if (profilesList.length === 0) {
        await fetchProfiles();
        profilesList = useProfilesStore.getState().profiles;
      }
      
      // If still no profiles, fetch directly
      if (profilesList.length === 0) {
        profilesList = await profilesApi.list();
      }
      
      const allSchedules: ScheduleWithProfile[] = [];
      
      // Load schedules for all profiles
      for (const profile of profilesList) {
        try {
          const profileSchedules = await schedulesApi.list(profile.id);
          const schedulesWithProfile = profileSchedules.map(s => ({
            ...s,
            profile_name: profile.name,
          }));
          allSchedules.push(...schedulesWithProfile);
        } catch (error) {
          console.error(`Error loading schedules for profile ${profile.id}:`, error);
        }
      }
      
      setSchedules(allSchedules);
    } catch (error: unknown) {
      console.error('Error loading schedules:', error);
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllSchedules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reload when profiles change
  useEffect(() => {
    if (profiles.length > 0 && !loading) {
      fetchAllSchedules();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profiles.length]);

  const handleAddSchedule = async () => {
    if (!selectedProfileId || selectedDays.length === 0) return;
    try {
      await schedulesApi.create(selectedProfileId as number, {
        days: selectedDays,
        from_time: useHours ? fromTime : undefined,
        to_time: useHours ? toTime : undefined,
      });
      setShowAddDialog(false);
      setSelectedDays([]);
      setSelectedProfileId('');
      setUseHours(false);
      setFromTime('18:00');
      setToTime('22:00');
      fetchAllSchedules();
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleDeleteSchedule = async (id: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק את התזמון הזה?')) return;
    try {
      await schedulesApi.delete(id);
      fetchAllSchedules();
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const toggleDay = (day: number) => {
    setSelectedDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    );
  };

  const getDaysList = (bitmask: number): number[] => {
    const days: number[] = [];
    for (let i = 0; i < 7; i++) {
      if (bitmask & (1 << i)) {
        days.push(i);
      }
    }
    return days;
  };

  const handleDialogClose = () => {
    setShowAddDialog(false);
    setSelectedDays([]);
    setUseHours(false);
    setFromTime('18:00');
    setToTime('22:00');
    // Don't reset selectedProfileId if it was set from navigation
  };

  if (loading && schedules.length === 0) {
    return (
      <Box>
        <Typography>טוען...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Page Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          תזמונים
        </Typography>
        <Typography variant="body2" color="text.secondary">
          ניהול תזמונים לכל הפרופילים
        </Typography>
      </Box>

      {/* Add Schedule Button */}
      <Box sx={{ mb: 3 }}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setSelectedProfileId('');
            setShowAddDialog(true);
          }}
        >
          הוסף תזמון
        </Button>
      </Box>

      {/* Schedules Table */}
      <Paper>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2, px: 2, pt: 2, pb: 1 }}>
          <TextField
            size="small"
            placeholder="חיפוש לפי פרופיל..."
            value={schedSearch}
            onChange={(e) => { setSchedSearch(e.target.value); setSchedPage(0); }}
            sx={{ minWidth: 220 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
        </Box>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sortDirection={schedOrderBy === 'profile' ? schedOrder : false} sx={{ fontWeight: 600 }}>
                  <TableSortLabel active={schedOrderBy === 'profile'} direction={schedOrderBy === 'profile' ? schedOrder : 'asc'} onClick={() => { setSchedOrderBy('profile'); setSchedOrder(schedOrderBy === 'profile' && schedOrder === 'asc' ? 'desc' : 'asc'); setSchedPage(0); }}>
                    פרופיל
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>ימים</TableCell>
                <TableCell sortDirection={schedOrderBy === 'from' ? schedOrder : false} sx={{ fontWeight: 600 }}>
                  <TableSortLabel active={schedOrderBy === 'from'} direction={schedOrderBy === 'from' ? schedOrder : 'asc'} onClick={() => { setSchedOrderBy('from'); setSchedOrder(schedOrderBy === 'from' && schedOrder === 'asc' ? 'desc' : 'asc'); setSchedPage(0); }}>
                    מ
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={schedOrderBy === 'to' ? schedOrder : false} sx={{ fontWeight: 600 }}>
                  <TableSortLabel active={schedOrderBy === 'to'} direction={schedOrderBy === 'to' ? schedOrder : 'asc'} onClick={() => { setSchedOrderBy('to'); setSchedOrder(schedOrderBy === 'to' && schedOrder === 'asc' ? 'desc' : 'asc'); setSchedPage(0); }}>
                    עד
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="center">פעולות</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(() => {
                const q = schedSearch.trim().toLowerCase();
                const filtered = !q
                  ? schedules
                  : schedules.filter((s) => (s.profile_name || '').toLowerCase().includes(q));
                if (filtered.length === 0) {
                  return (
                    <TableRow>
                      <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                          <Typography variant="body1" color="text.secondary">
                            {schedules.length === 0 ? 'אין תזמונים מוגדרים' : 'אין תוצאות לחיפוש'}
                          </Typography>
                          {schedules.length === 0 && (
                            <Button
                              variant="outlined"
                              startIcon={<AddIcon />}
                              onClick={() => {
                                setSelectedProfileId('');
                                setShowAddDialog(true);
                              }}
                            >
                              הוסף תזמון ראשון
                            </Button>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                }
                const sorted = [...filtered].sort((a, b) => {
                  let v = 0;
                  if (schedOrderBy === 'profile') v = (a.profile_name || '').localeCompare(b.profile_name || '');
                  else if (schedOrderBy === 'from') v = (a.from_time || '').localeCompare(b.from_time || '');
                  else if (schedOrderBy === 'to') v = (a.to_time || '').localeCompare(b.to_time || '');
                  return schedOrder === 'asc' ? v : -v;
                });
                const paginated = sorted.slice(schedPage * schedRowsPerPage, schedPage * schedRowsPerPage + schedRowsPerPage);
                return paginated.map((schedule) => {
                    const days = getDaysList(schedule.days_bitmask);
                    return (
                      <TableRow key={schedule.id} hover>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {schedule.profile_name || `פרופיל ${schedule.profile_id}`}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            {days.map((day) => (
                              <Chip key={day} label={DAYS_HEBREW[day]} size="small" />
                            ))}
                          </Box>
                        </TableCell>
                        <TableCell>
                          {schedule.from_time ? schedule.from_time : 'כל היום'}
                        </TableCell>
                        <TableCell>
                          {schedule.to_time ? schedule.to_time : 'כל היום'}
                        </TableCell>
                        <TableCell align="center">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleDeleteSchedule(schedule.id)}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    );
                  });
              })()}
            </TableBody>
          </Table>
          {(() => {
            const q = schedSearch.trim().toLowerCase();
            const filtered = !q ? schedules : schedules.filter((s) => (s.profile_name || '').toLowerCase().includes(q));
            const n = filtered.length;
            return n > 0 ? (
              <TablePagination
                component="div"
                count={n}
                page={schedPage}
                onPageChange={(_, p) => setSchedPage(p)}
                rowsPerPage={schedRowsPerPage}
                onRowsPerPageChange={(e) => { setSchedRowsPerPage(parseInt(e.target.value, 10)); setSchedPage(0); }}
                rowsPerPageOptions={SCHED_ROWS_OPTIONS}
                labelRowsPerPage="שורות בעמוד:"
                labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count}`}
              />
            ) : null;
          })()}
        </TableContainer>
      </Paper>

      {/* Add Schedule Dialog */}
      <Dialog open={showAddDialog} onClose={handleDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>תזמון חדש</DialogTitle>
        <DialogContent>
          <Box sx={{ mb: 3, mt: 2 }}>
            <FormControl fullWidth sx={{ mb: 3 }} required>
              <InputLabel>פרופיל</InputLabel>
              <Select
                value={selectedProfileId}
                onChange={(e) => setSelectedProfileId(e.target.value as number | '')}
                label="פרופיל"
              >
                {profiles.length === 0 ? (
                  <MenuItem disabled>טוען פרופילים...</MenuItem>
                ) : (
                  profiles.map((profile) => (
                    <MenuItem key={profile.id} value={profile.id}>
                      {profile.name}
                    </MenuItem>
                  ))
                )}
              </Select>
            </FormControl>

            <Typography variant="subtitle2" gutterBottom sx={{ mb: 2 }}>
              הפרופיל יפעל בימים:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {DAYS_HEBREW.map((day, index) => (
                <Chip
                  key={index}
                  label={day}
                  onClick={() => toggleDay(index)}
                  color={selectedDays.includes(index) ? 'primary' : 'default'}
                  variant={selectedDays.includes(index) ? 'filled' : 'outlined'}
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={useHours}
                  onChange={(e) => setUseHours(e.target.checked)}
                />
              }
              label="הגדר שעות פעילות"
            />
          </Box>

          {useHours && (
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <TextField
                label="מ"
                type="time"
                value={fromTime}
                onChange={(e) => setFromTime(e.target.value)}
                InputLabelProps={{ shrink: true }}
                fullWidth
              />
              <TextField
                label="עד"
                type="time"
                value={toTime}
                onChange={(e) => setToTime(e.target.value)}
                InputLabelProps={{ shrink: true }}
                fullWidth
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDialogClose}>ביטול</Button>
          <Button
            variant="contained"
            onClick={handleAddSchedule}
            disabled={selectedDays.length === 0 || !selectedProfileId}
          >
            הוסף
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SchedulesPage;
