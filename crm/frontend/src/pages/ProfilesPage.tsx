/**
 * Profiles page with tabs (like the image inspiration)
 */
import React, { useEffect, useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  Button,
  Box,
  Tabs,
  Tab,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Divider,
} from '@mui/material';
import { Add as AddIcon, Close as CloseIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useProfilesStore } from '../store/profilesStore';
import { RulesTable } from '../components/RulesTable';
import { rulesApi } from '../api/rules';
import type { Rule } from '../api/rules';

const ProfilesPage: React.FC = () => {
  const navigate = useNavigate();
  const { profiles, currentProfile, fetchProfiles, createProfile, updateProfile, deleteProfile, setCurrentProfile } = useProfilesStore();
  const [activeTab, setActiveTab] = useState(0);
  const [newProfileName, setNewProfileName] = useState('');
  const [newProfileMode, setNewProfileMode] = useState<'whitelist' | 'blacklist'>('whitelist');
  const [showNewProfile, setShowNewProfile] = useState(false);
  const [editingProfile, setEditingProfile] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editMode, setEditMode] = useState<'whitelist' | 'blacklist'>('whitelist');
  const [rules, setRules] = useState<Rule[]>([]);

  const selectedProfile = profiles[activeTab];

  const loadRules = async () => {
    if (!selectedProfile) return;
    try {
      const rulesData = await rulesApi.list(selectedProfile.id);
      setRules(rulesData);
    } catch (error: any) {
      console.error('Error loading rules:', error);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  useEffect(() => {
    if (selectedProfile) {
      loadRules();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile]);

  useEffect(() => {
    if (profiles.length > 0) {
      const currentIndex = profiles.findIndex(p => p.id === currentProfile?.id);
      if (currentIndex >= 0 && currentIndex !== activeTab) {
        setActiveTab(currentIndex);
      } else if (currentIndex < 0 && activeTab >= profiles.length) {
        // If current profile not found, go to first profile
        setActiveTab(0);
      }
    }
  }, [profiles, currentProfile, activeTab]);

  const handleCreateProfile = async () => {
    if (!newProfileName.trim()) return;
    try {
      const newProfile = await createProfile(newProfileName, newProfileMode);
      setNewProfileName('');
      setShowNewProfile(false);
      // Refresh profiles to get the updated list
      await fetchProfiles();
      // Set the new profile as active and switch to its tab
      if (newProfile) {
        setCurrentProfile(newProfile);
        // The profiles state will be updated by fetchProfiles
        // Use useEffect to handle tab switching after profiles update
        // This will be handled by the existing useEffect that watches profiles
      }
    } catch (error: any) {
      alert(`שגיאה: ${error.message}`);
    }
  };

  const handleEditProfile = (profile: typeof profiles[0]) => {
    setEditingProfile(profile.id);
    setEditName(profile.name);
    setEditMode(profile.mode);
  };

  const handleSaveEdit = async () => {
    if (!editingProfile || !editName.trim()) return;
    try {
      await updateProfile(editingProfile, editName, editMode);
      setEditingProfile(null);
    } catch (error: any) {
      alert(`שגיאה: ${error.message}`);
    }
  };

  const handleDeleteProfile = async (id: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק את הפרופיל הזה?')) return;
    try {
      await deleteProfile(id);
    } catch (error: any) {
      alert(`שגיאה: ${error.message}`);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        פרופילי סינון
      </Typography>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={activeTab}
            onChange={(_, v) => {
              setActiveTab(v);
              if (profiles[v]) {
                setCurrentProfile(profiles[v]);
              }
            }}
            variant="scrollable"
            scrollButtons="auto"
          >
            {profiles.map((profile) => (
              <Tab
                key={profile.id}
                label={profile.name}
                icon={profile.is_default ? undefined : (
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteProfile(profile.id);
                    }}
                    sx={{ ml: 1 }}
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                )}
                iconPosition="end"
              />
            ))}
            <Tab
              icon={<AddIcon />}
              onClick={() => setShowNewProfile(true)}
            />
          </Tabs>
        </Box>

        {/* Profile Details */}
        {selectedProfile && (
          <Box sx={{ p: 3 }}>
            <Box sx={{ mb: 2 }}>
              <TextField
                label="שם פרופיל"
                value={editingProfile === selectedProfile.id ? editName : selectedProfile.name}
                onChange={(e) => {
                  if (editingProfile === selectedProfile.id) {
                    setEditName(e.target.value);
                  } else {
                    handleEditProfile(selectedProfile);
                    setEditName(e.target.value);
                  }
                }}
                fullWidth
                sx={{ mb: 2 }}
              />
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  מצב עבודה
                </Typography>
                <Box
                  onClick={async () => {
                    const newMode = selectedProfile.mode === 'whitelist' ? 'blacklist' : 'whitelist';
                    try {
                      await updateProfile(selectedProfile.id, undefined, newMode);
                    } catch (error: any) {
                      alert(`שגיאה: ${error.message}`);
                    }
                  }}
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 1,
                    p: 1.5,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                >
                  <Chip
                    label={selectedProfile.mode === 'whitelist' ? 'רשימה לבנה + חריגים' : 'רשימה שחורה + חריגים'}
                    color={selectedProfile.mode === 'whitelist' ? 'success' : 'default'}
                    size="small"
                  />
                  <Typography variant="caption" color="text.secondary">
                    (לחץ לשינוי)
                  </Typography>
                </Box>
              </Box>
              {editingProfile === selectedProfile.id && (
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <Button variant="contained" onClick={handleSaveEdit}>
                    שמור
                  </Button>
                  <Button variant="outlined" onClick={() => setEditingProfile(null)}>
                    ביטול
                  </Button>
                </Box>
              )}
            </Box>

            <Divider sx={{ my: 3 }} />
            
            {/* Rules Section - Integrated */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                כללי סינון
              </Typography>
              <Paper sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {selectedProfile.mode === 'whitelist' ? (
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
                profileId={selectedProfile.id}
                rules={rules}
                onRefresh={loadRules}
              />
            </Box>
            
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                onClick={() => navigate('/schedules', { 
                  state: { openDialog: true, profileId: selectedProfile.id } 
                })}
              >
                הגדר זמנים
              </Button>
            </Box>
          </Box>
        )}
      </Paper>

      {/* New Profile Dialog */}
      <Dialog open={showNewProfile} onClose={() => setShowNewProfile(false)}>
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

export default ProfilesPage;
