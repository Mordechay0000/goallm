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
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { useProfilesStore } from '../store/profilesStore';
import { RulesTable } from '../components/RulesTable';
import { rulesApi } from '../api/rules';
import type { Rule } from '../api/rules';

const FilterManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const { profiles, currentProfile, fetchProfiles, setCurrentProfile } = useProfilesStore();
  const [activeTab, setActiveTab] = useState(0);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewProfile, setShowNewProfile] = useState(false);
  const [newProfileName, setNewProfileName] = useState('');
  const [newProfileMode, setNewProfileMode] = useState<'whitelist' | 'blacklist'>('whitelist');

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  useEffect(() => {
    if (profiles.length > 0) {
      const currentIndex = profiles.findIndex(p => p.id === currentProfile?.id);
      setActiveTab(currentIndex >= 0 ? currentIndex : 0);
      loadRules();
    }
  }, [profiles, currentProfile]);

  const loadRules = async () => {
    if (!currentProfile) return;
    setLoading(true);
    try {
      const rulesData = await rulesApi.list(currentProfile.id);
      setRules(rulesData);
    } catch (error: any) {
      console.error('Error loading rules:', error);
    } finally {
      setLoading(false);
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
    } catch (error: any) {
      alert(`שגיאה: ${error.message}`);
    }
  };

  const selectedProfile = profiles[activeTab];

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <IconButton onClick={() => navigate('/')} color="primary">
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h4" component="h1" fontWeight="bold">
            ניהול פילטרים
          </Typography>
        </Box>
        <Typography variant="body1" color="text.secondary">
          הוסף, ערוך ומחק כללי סינון לפרופילי הסינון שלך
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
                      <Chip label="ברירת מחדל" size="small" color="primary" />
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
                label={selectedProfile.mode === 'whitelist' ? 'רשימה לבנה + חריגים' : 'רשימה שחורה + חריגים'}
                color={selectedProfile.mode === 'whitelist' ? 'success' : 'error'}
                sx={{ mb: 2 }}
              />
              <Typography variant="body2" color="text.secondary" paragraph>
                {selectedProfile.mode === 'whitelist' ? (
                  <>כל האתרים במערכת <strong style={{ color: '#4caf50' }}>פתוחים</strong> למעט האתרים הרשומים למטה:</>
                ) : (
                  <>כל האתרים במערכת <strong style={{ color: '#f44336' }}>חסומים</strong> למעט האתרים הרשומים למטה:</>
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
              <MenuItem value="whitelist">רשימה לבנה + חריגים</MenuItem>
              <MenuItem value="blacklist">רשימה שחורה + חריגים</MenuItem>
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
