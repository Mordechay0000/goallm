/**
 * Dashboard - Minimal admin dashboard
 * Functional, clear hierarchy, no visual effects
 */
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  Divider,
  TableSortLabel,
  TablePagination,
  TextField,
  InputAdornment,
} from '@mui/material';
import {
  FilterList as FilterIcon,
  Schedule as ScheduleIcon,
  Security as SecurityIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import { useProfilesStore } from '../store/profilesStore';
import { rulesApi } from '../api/rules';
import { schedulesApi } from '../api/schedules';

type ProfileOrder = 'asc' | 'desc';
type ProfileSortBy = 'name' | 'mode';
const PROFILE_ROWS_OPTIONS = [10, 25, 50];

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { profiles, currentProfile, fetchProfiles } = useProfilesStore();
  const [stats, setStats] = React.useState({
    totalRules: 0,
    totalSchedules: 0,
  });
  const [profileOrder, setProfileOrder] = React.useState<ProfileOrder>('asc');
  const [profileOrderBy, setProfileOrderBy] = React.useState<ProfileSortBy>('name');
  const [profilePage, setProfilePage] = React.useState(0);
  const [profileRowsPerPage, setProfileRowsPerPage] = React.useState(10);
  const [profileSearch, setProfileSearch] = React.useState('');

  const loadStats = React.useCallback(async () => {
    try {
      let totalRules = 0;
      let totalSchedules = 0;

      for (const profile of profiles) {
        const [rules, schedules] = await Promise.all([
          rulesApi.list(profile.id).catch(() => []),
          schedulesApi.list(profile.id).catch(() => []),
        ]);
        totalRules += rules.length;
        totalSchedules += schedules.length;
      }

      setStats({
        totalRules,
        totalSchedules,
      });
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  }, [profiles]);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  useEffect(() => {
    if (profiles.length > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- load stats when profiles change; setState in async callback
      loadStats();
    }
  }, [profiles, loadStats]);

  return (
    <Box>
      {/* Page Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          ברוך הבא
        </Typography>
        <Typography variant="body2" color="text.secondary">
          סיכום ההגדרות והמספרים שלך
        </Typography>
      </Box>

      {/* Stats Grid */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' }, gap: 2, mb: 4 }}>
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <FilterIcon color="primary" />
            <Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {stats.totalRules}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                אתרים שהגדרת (חסום או פתוח)
              </Typography>
            </Box>
          </Box>
        </Paper>

        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <ScheduleIcon color="primary" />
            <Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {stats.totalSchedules}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                שעות פעילות
              </Typography>
            </Box>
          </Box>
        </Paper>

        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <SecurityIcon color="primary" />
            <Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {profiles.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                פרופילים
              </Typography>
            </Box>
          </Box>
        </Paper>
      </Box>

      {/* Active Profile */}
      <Paper sx={{ mb: 4 }}>
        <Box sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
            הפרופיל שפעיל כרגע
          </Typography>
          <Divider sx={{ mb: 3 }} />
          {currentProfile ? (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  {currentProfile.name}
                </Typography>
                <Chip
                  label={currentProfile.mode === 'whitelist' ? 'הכל חסום – אוסיף פתיחות' : 'הכל פתוח – אוסיף חסימות'}
                  color={currentProfile.mode === 'whitelist' ? 'default' : 'success'}
                  size="small"
                />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                {currentProfile.mode === 'whitelist'
                  ? 'כל האתרים חסומים – פותח רק את האתרים שתוסיף'
                  : 'כל האתרים פתוחים – חוסם רק את האתרים שתוסיף'}
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  onClick={() => navigate('/profiles')}
                >
                  לערוך את ההגדרות
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => navigate('/schedules', { 
                    state: { openDialog: true, profileId: currentProfile.id } 
                  })}
                >
                  להגדיר שעות פעילות
                </Button>
              </Box>
            </Box>
          ) : (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                עדיין לא הגדרת פרופיל. אפשר ליצור אחד ולבחור אילו אתרים לחסום ואילו לפתוח.
              </Typography>
              <Button
                variant="contained"
                onClick={() => navigate('/profiles')}
              >
                ליצור פרופיל חדש
              </Button>
            </Box>
          )}
        </Box>
      </Paper>

      {/* Profiles List */}
      {profiles.length > 0 && (
        <Paper>
          <Box sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
              כל הפרופילים שלך
            </Typography>
            <Divider sx={{ mb: 3 }} />
            <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2, mb: 2 }}>
              <TextField
                size="small"
                placeholder="לחפש לפי שם..."
                value={profileSearch}
                onChange={(e) => { setProfileSearch(e.target.value); setProfilePage(0); }}
                sx={{ minWidth: 240 }}
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
                    <TableCell sortDirection={profileOrderBy === 'name' ? profileOrder : false} sx={{ fontWeight: 600 }}>
                      <TableSortLabel active={profileOrderBy === 'name'} direction={profileOrderBy === 'name' ? profileOrder : 'asc'} onClick={() => { setProfileOrderBy('name'); setProfileOrder(profileOrderBy === 'name' && profileOrder === 'asc' ? 'desc' : 'asc'); setProfilePage(0); }}>
                        שם פרופיל
                      </TableSortLabel>
                    </TableCell>
                    <TableCell sortDirection={profileOrderBy === 'mode' ? profileOrder : false} sx={{ fontWeight: 600 }}>
                      <TableSortLabel active={profileOrderBy === 'mode'} direction={profileOrderBy === 'mode' ? profileOrder : 'asc'} onClick={() => { setProfileOrderBy('mode'); setProfileOrder(profileOrderBy === 'mode' && profileOrder === 'asc' ? 'desc' : 'asc'); setProfilePage(0); }}>
                        מצב
                      </TableSortLabel>
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>אופן עבודה</TableCell>
                    <TableCell sx={{ fontWeight: 600 }} align="right">מה אפשר לעשות</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(() => {
                    const q = profileSearch.trim().toLowerCase();
                    const filtered = !q ? profiles : profiles.filter((p) => (p.name || '').toLowerCase().includes(q));
                    if (filtered.length === 0) {
                      return (
                        <TableRow>
                          <TableCell colSpan={4} align="center">
                            {profiles.length === 0 ? 'עדיין אין פרופילים' : 'לא נמצאו תוצאות'}
                          </TableCell>
                        </TableRow>
                      );
                    }
                    const sorted = [...filtered].sort((a, b) => {
                      let v = 0;
                      if (profileOrderBy === 'name') v = (a.name || '').localeCompare(b.name || '');
                      else v = (a.mode || '').localeCompare(b.mode || '');
                      return profileOrder === 'asc' ? v : -v;
                    });
                    const paginated = sorted.slice(profilePage * profileRowsPerPage, profilePage * profileRowsPerPage + profileRowsPerPage);
                    return paginated.map((profile) => (
                      <TableRow key={profile.id} hover>
                        <TableCell>{profile.name}</TableCell>
                        <TableCell>
                          <Chip
                            label={profile.is_default ? 'פעיל' : 'לא פעיל'}
                            color={profile.is_default ? 'primary' : 'default'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={profile.mode === 'whitelist' ? 'הכל חסום – אוסיף פתיחות' : 'הכל פתוח – אוסיף חסימות'}
                            variant="outlined"
                            size="small"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Button
                            size="small"
                            onClick={() => navigate('/profiles')}
                          >
                            לערוך
                          </Button>
                          <Button
                            size="small"
                            onClick={() => navigate('/schedules', { 
                              state: { openDialog: true, profileId: profile.id } 
                            })}
                          >
                            שעות פעילות
                          </Button>
                        </TableCell>
                      </TableRow>
                    ));
                  })()}
                </TableBody>
              </Table>
            </TableContainer>
            {(() => {
              const q = profileSearch.trim().toLowerCase();
              const filtered = !q ? profiles : profiles.filter((p) => (p.name || '').toLowerCase().includes(q));
              const n = filtered.length;
              return n > 0 ? (
                <TablePagination
                  component="div"
                  count={n}
                  page={profilePage}
                  onPageChange={(_, p) => setProfilePage(p)}
                  rowsPerPage={profileRowsPerPage}
                  onRowsPerPageChange={(e) => { setProfileRowsPerPage(parseInt(e.target.value, 10)); setProfilePage(0); }}
                  rowsPerPageOptions={PROFILE_ROWS_OPTIONS}
                  labelRowsPerPage="שורות בעמוד:"
                  labelDisplayedRows={({ from, to, count }) => `${from}–${to} מתוך ${count}`}
                />
              ) : null;
            })()}
          </Box>
        </Paper>
      )}
    </Box>
  );
};

export default HomePage;
