/**
 * Admin Layout - Minimal, functional design for admin application
 * Sidebar navigation with clear hierarchy
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  ListSubheader,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Menu,
  MenuItem,
  Badge,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Security as SecurityIcon,
  Schedule as ScheduleIcon,
  Settings as SettingsIcon,
  Person as PersonIcon,
  People as PeopleIcon,
  Logout as LogoutIcon,
  Public as PublicIcon,
  Assignment as AssignmentIcon,
  Tune as TuneIcon,
  Link as LinkIcon,
  QuestionAnswer as QuestionAnswerIcon,
  Build as BuildIcon,
  InsertDriveFile as InsertDriveFileIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../store/authStore';
import { getAvatarUrl } from '../api/auth';
import { supportApi } from '../api/support';
import { BRAND } from '../brand';
import BrandLogo from './BrandLogo';

const DRAWER_WIDTH = 212;

interface NavItem {
  label: string;
  icon: React.ReactNode;
  path: string;
  children?: NavItem[];
}

const navItems: NavItem[] = [
  {
    label: 'הבית',
    icon: <DashboardIcon />,
    path: '/',
  },
  {
    label: 'הגדרות הסינון שלי',
    icon: <SecurityIcon />,
    path: '/profiles',
  },
  {
    label: 'שעות פעילות',
    icon: <ScheduleIcon />,
    path: '/schedules',
  },
  {
    label: 'בקשות ששלחתי',
    icon: <AssignmentIcon />,
    path: '/requests',
  },
  {
    label: 'פניות שלי',
    icon: <QuestionAnswerIcon />,
    path: '/support',
  },
  {
    label: 'המכשירים שלי',
    icon: <LinkIcon />,
    path: '/connections',
  },
  {
    label: 'כלים',
    icon: <BuildIcon />,
    path: '/tools',
  },
];

const AdminLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [supportStats, setSupportStats] = useState<{ tickets_with_replies: number; admin_tickets_with_replies?: number }>({ tickets_with_replies: 0 });
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  useEffect(() => {
    if (!user) return;
    supportApi.getStats().then(setSupportStats).catch(() => {});
  }, [user]);
  // Refresh support stats when opening the support list (so badge updates after marking read)
  const isSupportList = location.pathname === '/support' || location.pathname === '/admin/support';
  useEffect(() => {
    if (!user || !isSupportList) return;
    supportApi.getStats().then(setSupportStats).catch(() => {});
  }, [user, isSupportList]);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
    navigate('/login');
  };

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  const drawer = (
    <Box>
      <Toolbar
        className="brand-signature"
        sx={{
          minHeight: '72px !important',
          flexDirection: 'column',
          alignItems: 'flex-start',
          justifyContent: 'center',
          px: 1.5,
          pt: 1.5,
          pb: 1.5,
          borderBottom: 'none',
        }}
      >
        <BrandLogo showName size="sidebar" />
        <Typography
          variant="caption"
          sx={{ color: 'text.secondary', fontWeight: 500, mt: 0.5 }}
        >
          {BRAND.tagline}
        </Typography>
      </Toolbar>
      <Divider />
      <List sx={{ pt: 1, pb: 1 }} subheader={<ListSubheader component="div" sx={{ lineHeight: 2, fontWeight: 600, fontSize: '0.75rem', color: 'text.secondary', letterSpacing: '0.02em' }}>ניווט</ListSubheader>}>
        {navItems.map((item) => {
          const showSupportBadge = item.path === '/support' && (supportStats.tickets_with_replies ?? 0) > 0;
          return (
            <ListItem key={item.path} disablePadding sx={{ mb: 0 }}>
              <ListItemButton
                selected={isActive(item.path)}
                onClick={() => {
                  navigate(item.path);
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  py: 1,
                  px: 2,
                  '&.Mui-selected': {
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                    boxShadow: 'inset 0 0 24px rgba(30, 58, 95, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 44, mr: 1.5 }}>
                  {showSupportBadge ? (
                    <Badge badgeContent={supportStats.tickets_with_replies} color="primary">
                      {item.icon}
                    </Badge>
                  ) : (
                    item.icon
                  )}
                </ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
          );
        })}
        {user?.is_admin && (
          <>
            <Divider sx={{ my: 1 }} />
            <List sx={{ pt: 0, pb: 1 }} subheader={<ListSubheader component="div" sx={{ lineHeight: 2, fontWeight: 600, fontSize: '0.75rem', color: 'text.secondary', letterSpacing: '0.02em' }}>ניהול</ListSubheader>}>
            <ListItem disablePadding sx={{ mb: 0 }}>
              <ListItemButton
                selected={isActive('/admin/users')}
                onClick={() => {
                  navigate('/admin/users');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  py: 1,
                  px: 2,
                  '&.Mui-selected': {
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                    boxShadow: 'inset 0 0 24px rgba(30, 58, 95, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 44, mr: 1.5 }}>
                  <PeopleIcon />
                </ListItemIcon>
                <ListItemText
                  primary="משתמשים (אדמין)"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/users') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding sx={{ mb: 0 }}>
              <ListItemButton
                selected={isActive('/admin/requests')}
                onClick={() => {
                  navigate('/admin/requests');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  py: 1,
                  px: 2,
                  '&.Mui-selected': {
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                    boxShadow: 'inset 0 0 24px rgba(30, 58, 95, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 44, mr: 1.5 }}>
                  <SecurityIcon />
                </ListItemIcon>
                <ListItemText
                  primary="בקשות שהתקבלו (אדמין)"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/requests') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding sx={{ mb: 0 }}>
              <ListItemButton
                selected={isActive('/admin/global-rules')}
                onClick={() => {
                  navigate('/admin/global-rules');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  py: 1,
                  px: 2,
                  '&.Mui-selected': {
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                    boxShadow: 'inset 0 0 24px rgba(30, 58, 95, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 44, mr: 1.5 }}>
                  <PublicIcon />
                </ListItemIcon>
                <ListItemText
                  primary="רשימת האתרים הגלובלית (אדמין)"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/global-rules') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding sx={{ mb: 0 }}>
              <ListItemButton
                selected={isActive('/admin/global-files')}
                onClick={() => {
                  navigate('/admin/global-files');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  py: 1,
                  px: 2,
                  '&.Mui-selected': {
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                    boxShadow: 'inset 0 0 24px rgba(30, 58, 95, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 44, mr: 1.5 }}>
                  <InsertDriveFileIcon />
                </ListItemIcon>
                <ListItemText
                  primary="רשימת הקבצים הגלובלית (אדמין)"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/global-files') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding sx={{ mb: 0 }}>
              <ListItemButton
                selected={isActive('/admin/filter-switches')}
                onClick={() => {
                  navigate('/admin/filter-switches');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  py: 1,
                  px: 2,
                  '&.Mui-selected': {
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                    boxShadow: 'inset 0 0 24px rgba(30, 58, 95, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 44, mr: 1.5 }}>
                  <TuneIcon />
                </ListItemIcon>
                <ListItemText
                  primary="הפעלת סינונים (אדמין)"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/filter-switches') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding sx={{ mb: 0 }}>
              <ListItemButton
                selected={isActive('/admin/support')}
                onClick={() => {
                  navigate('/admin/support');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  py: 1,
                  px: 2,
                  '&.Mui-selected': {
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                    boxShadow: 'inset 0 0 24px rgba(30, 58, 95, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 44, mr: 1.5 }}>
                  {(supportStats.admin_tickets_with_replies ?? 0) > 0 ? (
                    <Badge badgeContent={supportStats.admin_tickets_with_replies} color="primary">
                      <QuestionAnswerIcon />
                    </Badge>
                  ) : (
                    <QuestionAnswerIcon />
                  )}
                </ListItemIcon>
                <ListItemText
                  primary="פניות שהתקבלו (אדמין)"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/support') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            </List>
          </>
        )}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { sm: `${DRAWER_WIDTH}px` },
        }}
        elevation={0}
      >
        <Toolbar sx={{ minHeight: '64px !important' }}>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography
            variant="h6"
            component="div"
            sx={{
              fontWeight: 700,
              fontSize: '1.1rem',
              color: 'primary.main',
              letterSpacing: '-0.02em',
              display: { xs: 'none', sm: 'block' },
              mr: 2,
            }}
          >
            {BRAND.appName}
          </Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ display: { xs: 'none', sm: 'block' } }}>
              {user?.first_name && user?.last_name
                ? `${user.first_name} ${user.last_name}`
                : user?.phone || 'משתמש'}
            </Typography>
            <IconButton onClick={handleMenuOpen} size="small">
              <Avatar
                src={user?.avatar_url ? getAvatarUrl(user.avatar_url) : undefined}
                sx={{ width: 32, height: 32 }}
              >
                {user?.first_name?.[0] || user?.last_name?.[0] || 'U'}
              </Avatar>
            </IconButton>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'left',
              }}
              transformOrigin={{
                vertical: 'top',
                horizontal: 'left',
              }}
            >
              <MenuItem onClick={() => { navigate('/profile/edit'); handleMenuClose(); }}>
                <ListItemIcon>
                  <PersonIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>הפרופיל שלי</ListItemText>
              </MenuItem>
              <MenuItem onClick={() => { navigate('/profile/edit'); handleMenuClose(); }}>
                <ListItemIcon>
                  <SettingsIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>הגדרות החשבון</ListItemText>
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}>
                <ListItemIcon>
                  <LogoutIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>יציאה מהחשבון</ListItemText>
              </MenuItem>
            </Menu>
          </Box>
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ width: { sm: DRAWER_WIDTH }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              borderLeft: '1px solid',
              borderColor: 'divider',
            },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              borderLeft: '1px solid',
              borderColor: 'divider',
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          pt: 0,
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          backgroundColor: 'background.default',
          minHeight: '100vh',
        }}
        className="main-content"
      >
        <Toolbar sx={{ minHeight: '64px !important' }} />
        <Box sx={{ pt: 3 }} className="container-content">{children}</Box>
      </Box>
    </Box>
  );
};

export default AdminLayout;
