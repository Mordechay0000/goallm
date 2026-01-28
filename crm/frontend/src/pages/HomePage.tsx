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
} from '@mui/material';
import {
  FilterList as FilterIcon,
  Schedule as ScheduleIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import { useProfilesStore } from '../store/profilesStore';
import { rulesApi } from '../api/rules';
import { schedulesApi } from '../api/schedules';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { profiles, currentProfile, fetchProfiles } = useProfilesStore();
  const [stats, setStats] = React.useState({
    totalRules: 0,
    totalSchedules: 0,
  });

  useEffect(() => {
    fetchProfiles();
    loadStats();
  }, [fetchProfiles]);

  const loadStats = async () => {
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
  };

  useEffect(() => {
    if (profiles.length > 0) {
      loadStats();
    }
  }, [profiles]);

  return (
    <Box>
      {/* Page Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          לוח בקרה
        </Typography>
        <Typography variant="body2" color="text.secondary">
          סקירה כללית של המערכת
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
                כללי סינון
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
                תזמונים
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
                פרופילי סינון
              </Typography>
            </Box>
          </Box>
        </Paper>
      </Box>

      {/* Active Profile */}
      <Paper sx={{ mb: 4 }}>
        <Box sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
            פרופיל פעיל
          </Typography>
          <Divider sx={{ mb: 3 }} />
          {currentProfile ? (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  {currentProfile.name}
                </Typography>
                <Chip
                  label={currentProfile.mode === 'whitelist' ? 'רשימה לבנה' : 'רשימה שחורה'}
                  color={currentProfile.mode === 'whitelist' ? 'success' : 'default'}
                  size="small"
                />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                {currentProfile.mode === 'whitelist'
                  ? 'כל האתרים פתוחים למעט אלו שחסומים'
                  : 'כל האתרים חסומים למעט אלו שפתוחים'}
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  onClick={() => navigate('/profiles')}
                >
                  ניהול פרופיל
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => navigate('/schedules', { 
                    state: { openDialog: true, profileId: currentProfile.id } 
                  })}
                >
                  הגדר זמנים
                </Button>
              </Box>
            </Box>
          ) : (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                אין פרופיל פעיל
              </Typography>
              <Button
                variant="contained"
                onClick={() => navigate('/profiles')}
              >
                צור פרופיל חדש
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
              פרופילי סינון
            </Typography>
            <Divider sx={{ mb: 3 }} />
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>שם פרופיל</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>מצב</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>סוג</TableCell>
                    <TableCell sx={{ fontWeight: 600 }} align="right">פעולות</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {profiles.map((profile) => (
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
                          label={profile.mode === 'whitelist' ? 'רשימה לבנה' : 'רשימה שחורה'}
                          variant="outlined"
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          onClick={() => navigate('/profiles')}
                        >
                          ניהול
                        </Button>
                        <Button
                          size="small"
                          onClick={() => navigate('/schedules', { 
                            state: { openDialog: true, profileId: profile.id } 
                          })}
                        >
                          תזמונים
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </Paper>
      )}
    </Box>
  );
};

export default HomePage;
