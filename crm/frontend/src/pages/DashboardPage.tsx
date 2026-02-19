/**
 * Dashboard page - shows active profile and quick actions
 */
import React, { useEffect } from 'react';
import {
  Container,
  Typography,
  Button,
  Box,
  Card,
  CardContent,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useProfilesStore } from '../store/profilesStore';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { currentProfile, fetchProfiles } = useProfilesStore();

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  return (
    <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, mb: 4, px: { xs: 2 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
            לוח בקרה
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {user?.email}
          </Typography>
        </Box>
        <Button variant="outlined" onClick={logout}>
          התנתק
        </Button>
      </Box>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            פרופיל פעיל כעת
          </Typography>
          {currentProfile ? (
            <Box>
              <Typography variant="body1" sx={{ mb: 2 }}>
                <strong>{currentProfile.name}</strong> ({currentProfile.mode === 'whitelist' ? 'הכל חסום – אוסיף פתיחות' : 'הכל פתוח – אוסיף חסימות'})
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  onClick={() => navigate(`/profiles/${currentProfile.id}/rules`)}
                >
                  ערוך אתרים
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => navigate(`/profiles/${currentProfile.id}/schedules`)}
                >
                  הגדר זמנים
                </Button>
              </Box>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              אין פרופיל פעיל
            </Typography>
          )}
        </CardContent>
      </Card>

      <Button
        variant="contained"
        onClick={() => navigate('/profiles')}
        size="large"
      >
        ניהול פרופילים
      </Button>
    </Container>
  );
};

export default DashboardPage;
