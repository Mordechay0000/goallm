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
  Alert,
} from '@mui/material';
import { Add as AddIcon, Close as CloseIcon, ExitToApp as ExitIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useProfilesStore } from '../store/profilesStore';
import { useManagedUserStore } from '../store/managedUserStore';
import { useAuthStore } from '../store/authStore';
import { RulesTable } from '../components/RulesTable';
import { rulesApi, resolverApi } from '../api/rules';
import { adminApi } from '../api/admin';
import type { Rule } from '../api/rules';
import { Lock as LockIcon } from '@mui/icons-material';
import { Tooltip } from '@mui/material';

const ProfilesPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { managedUserId, managedUserPhone, clearManagedUser } = useManagedUserStore();
  const { profiles, currentProfile, fetchProfiles, createProfile, updateProfile, deleteProfile, setCurrentProfile } = useProfilesStore();
  const [activeTab, setActiveTab] = useState(0);
  const [newProfileName, setNewProfileName] = useState('');
  const [newProfileMode, setNewProfileMode] = useState<'whitelist' | 'blacklist'>('whitelist');
  const [showNewProfile, setShowNewProfile] = useState(false);
  const [editingProfile, setEditingProfile] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editMode, setEditMode] = useState<'whitelist' | 'blacklist'>('whitelist');
  const [rules, setRules] = useState<Rule[]>([]);
  const [lockedSettings, setLockedSettings] = useState<string[]>([]);
  const [coreMode, setCoreMode] = useState<string | null>(null);

  const selectedProfile = profiles[activeTab];

  const loadCoreMode = () => {
    resolverApi.getCoreMode().then((r) => setCoreMode(r.core_mode ?? null)).catch(() => setCoreMode(null));
  };

  const loadRules = async () => {
    if (!selectedProfile) return;
    try {
      const rulesData = await rulesApi.list(selectedProfile.id, managedUserId ?? undefined);
      setRules(rulesData);
    } catch (error: unknown) {
      console.error('Error loading rules:', error);
    }
  };

  useEffect(() => {
    fetchProfiles(managedUserId ?? undefined);
  }, [fetchProfiles, managedUserId]);

  useEffect(() => {
    if (managedUserId != null && user?.is_admin) {
      adminApi.getLockedSettings(managedUserId).then(setLockedSettings).catch(() => setLockedSettings([]));
    } else {
      setLockedSettings([]);
    }
  }, [managedUserId, user?.is_admin]);

  useEffect(() => {
    if (selectedProfile) {
      loadRules();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile]);

  useEffect(() => {
    loadCoreMode();
  }, []);

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
      const newProfile = await createProfile(newProfileName, newProfileMode, managedUserId ?? undefined);
      setNewProfileName('');
      setShowNewProfile(false);
      // Refresh profiles to get the updated list
      await fetchProfiles(managedUserId ?? undefined);
      // Set the new profile as active and switch to its tab
      if (newProfile) {
        setCurrentProfile(newProfile);
        // The profiles state will be updated by fetchProfiles
        // Use useEffect to handle tab switching after profiles update
        // This will be handled by the existing useEffect that watches profiles
      }
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
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
      await updateProfile(editingProfile, editName, editMode, managedUserId ?? undefined);
      setEditingProfile(null);
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleDeleteProfile = async (id: number) => {
    if (!confirm('למחוק את הפרופיל הזה?')) return;
    try {
      await deleteProfile(id, managedUserId ?? undefined);
    } catch (error: unknown) {
      alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleExitManage = () => {
    clearManagedUser();
    navigate('/admin/users');
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {managedUserId != null && managedUserPhone && (
        <Alert
          severity="info"
          action={
            <Button color="inherit" size="small" startIcon={<ExitIcon />} onClick={handleExitManage}>
              יציאה
            </Button>
          }
          sx={{ mb: 2 }}
        >
          הפרופילים של {managedUserPhone}
        </Alert>
      )}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          {managedUserId != null && managedUserPhone ? `הפרופילים של ${managedUserPhone}` : 'הפרופילים שלי'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          ניהול פרופילי סינון – כל פרופיל מגדיר אילו אתרים חסומים או פתוחים.
        </Typography>
      </Box>

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
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                <TextField
                  label="שם פרופיל"
                  value={editingProfile === selectedProfile.id ? editName : selectedProfile.name}
                  onChange={(e) => {
                    if (selectedProfile.is_default || lockedSettings.includes('profile_name')) return;
                    if (editingProfile === selectedProfile.id) {
                      setEditName(e.target.value);
                    } else {
                      handleEditProfile(selectedProfile);
                      setEditName(e.target.value);
                    }
                  }}
                  fullWidth
                  sx={{ mb: 2 }}
                  disabled={!!selectedProfile.is_default || lockedSettings.includes('profile_name')}
                  helperText={
                    selectedProfile.is_default
                      ? 'לא ניתן לשנות את שם הפרופיל של ברירת המחדל'
                      : lockedSettings.includes('profile_name')
                        ? 'נחסם על ידי ההנהלה'
                        : undefined
                  }
                  InputProps={{
                    endAdornment: lockedSettings.includes('profile_name') ? (
                      <Tooltip title="נחסם על ידי ההנהלה"><LockIcon fontSize="small" color="disabled" /></Tooltip>
                    ) : undefined,
                  }}
                />
              </Box>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  מצב עבודה
                  {lockedSettings.includes('profile_mode') && (
                    <Tooltip title="נחסם על ידי ההנהלה">
                      <LockIcon fontSize="small" color="disabled" sx={{ ml: 0.5, verticalAlign: 'middle' }} />
                    </Tooltip>
                  )}
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.5 }}>
                  <Chip
                    label={selectedProfile.mode === 'whitelist' ? 'הכל חסום – אוסיף פתיחות' : 'הכל פתוח – אוסיף חסימות'}
                    color={selectedProfile.mode === 'whitelist' ? 'default' : 'success'}
                    size="small"
                    onClick={lockedSettings.includes('profile_mode') ? undefined : async () => {
                      const newMode = selectedProfile.mode === 'whitelist' ? 'blacklist' : 'whitelist';
                      try {
                        await updateProfile(selectedProfile.id, undefined, newMode, managedUserId ?? undefined);
                        loadCoreMode();
                      } catch (error: unknown) {
                        alert(`שגיאה: ${error instanceof Error ? error.message : String(error)}`);
                      }
                    }}
                    sx={{
                      cursor: lockedSettings.includes('profile_mode') ? 'not-allowed' : 'pointer',
                      opacity: lockedSettings.includes('profile_mode') ? 0.7 : 1,
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {lockedSettings.includes('profile_mode') ? 'נחסם על ידי ההנהלה' : 'לחץ לשינוי מצב'}
                  </Typography>
                  {coreMode != null && (
                    <Typography variant="caption" color="text.secondary">(מצב בפרוקסי: {coreMode})</Typography>
                  )}
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
                    <>כל האתרים <strong>חסומים</strong> במצב הזה. למטה תוסיף רק את האתרים שתרצה לפתוח.</>
                  ) : (
                    <>כל האתרים <strong>פתוחים</strong> במצב הזה. למטה תוסיף רק את האתרים שתרצה לחסום.</>
                  )}
                </Typography>
              </Paper>
              <RulesTable
                profileId={selectedProfile.id}
                rules={rules}
                onRefresh={loadRules}
                managedUserId={managedUserId ?? undefined}
                rulesLocked={lockedSettings.includes('rules')}
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

export default ProfilesPage;
