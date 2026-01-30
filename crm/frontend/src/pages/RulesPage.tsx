/**
 * Rules page - the heart of the system
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Box,
  Button,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import { RulesTable } from '../components/RulesTable';
import { rulesApi } from '../api/rules';
import { profilesApi } from '../api/profiles';
import type { Rule } from '../api/rules';
import type { Profile } from '../api/profiles';

const RulesPage: React.FC = () => {
  const { profileId } = useParams<{ profileId: string }>();
  const navigate = useNavigate();
  const [rules, setRules] = useState<Rule[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    if (!profileId) return;
    try {
      const [rulesData, profileData] = await Promise.all([
        rulesApi.list(parseInt(profileId)),
        profilesApi.get(parseInt(profileId)),
      ]);
      setRules(rulesData);
      setProfile(profileData);
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch when profileId changes
  }, [profileId]);

  if (loading) {
    return <Container>טוען...</Container>;
  }

  if (!profile) {
    return <Container>פרופיל לא נמצא</Container>;
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/profiles')}>
          חזרה לפרופילים
        </Button>
        <Typography variant="h4">
          חוקים - {profile.name}
        </Typography>
      </Box>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="body1" sx={{ mb: 2 }}>
          {profile.mode === 'whitelist' ? (
            <>
              כל האתרים במערכת <strong style={{ color: '#4caf50' }}>פתוחים</strong> למעט האתרים הרשומים למטה:
            </>
          ) : (
            <>
              כל האתרים במערכת <strong style={{ color: '#f44336' }}>חסומים</strong> למעט האתרים הרשומים למטה:
            </>
          )}
        </Typography>
      </Paper>

      <RulesTable
        profileId={profile.id}
        rules={rules}
        onRefresh={fetchData}
      />
    </Container>
  );
};

export default RulesPage;
