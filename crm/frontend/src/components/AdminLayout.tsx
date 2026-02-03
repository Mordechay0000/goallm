/**
 * Admin Layout - Minimal, functional design for admin application
 * Sidebar navigation with clear hierarchy
 */
import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
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
} from '@mui/icons-material';
import { useAuthStore } from '../store/authStore';
import { getAvatarUrl } from '../api/auth';

const DRAWER_WIDTH = 260;

interface NavItem {
  label: string;
  icon: React.ReactNode;
  path: string;
  children?: NavItem[];
}

const navItems: NavItem[] = [
  {
    label: 'לוח בקרה',
    icon: <DashboardIcon />,
    path: '/',
  },
  {
    label: 'פרופילי סינון וחוקים',
    icon: <SecurityIcon />,
    path: '/profiles',
  },
  {
    label: 'תזמונים',
    icon: <ScheduleIcon />,
    path: '/schedules',
  },
  {
    label: 'בקשות שלי',
    icon: <AssignmentIcon />,
    path: '/requests',
  },
];

const AdminLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

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
        sx={{
          minHeight: '64px !important',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 600, fontSize: '1.1rem' }}>
          ניהול סינון
        </Typography>
      </Toolbar>
      <Divider />
      <List sx={{ pt: 1 }}>
        {navItems.map((item) => (
          <ListItem key={item.path} disablePadding>
            <ListItemButton
              selected={isActive(item.path)}
              onClick={() => {
                navigate(item.path);
                setMobileOpen(false);
              }}
              sx={{
                minHeight: 48,
                '&.Mui-selected': {
                  backgroundColor: 'action.selected',
                  borderRight: '3px solid',
                  borderColor: 'primary.main',
                  '&:hover': {
                    backgroundColor: 'action.selected',
                  },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          </ListItem>
        ))}
        {user?.is_admin && (
          <>
            <ListItem disablePadding>
              <ListItemButton
                selected={isActive('/admin/users')}
                onClick={() => {
                  navigate('/admin/users');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  '&.Mui-selected': {
                    backgroundColor: 'action.selected',
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <PeopleIcon />
                </ListItemIcon>
                <ListItemText
                  primary="ניהול משתמשים"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/users') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding>
              <ListItemButton
                selected={isActive('/admin/requests')}
                onClick={() => {
                  navigate('/admin/requests');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  '&.Mui-selected': {
                    backgroundColor: 'action.selected',
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <SecurityIcon />
                </ListItemIcon>
                <ListItemText
                  primary="בקשות משתמשים"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/requests') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding>
              <ListItemButton
                selected={isActive('/admin/global-rules')}
                onClick={() => {
                  navigate('/admin/global-rules');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  '&.Mui-selected': {
                    backgroundColor: 'action.selected',
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <PublicIcon />
                </ListItemIcon>
                <ListItemText
                  primary="רשימה גלובלית"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/global-rules') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding>
              <ListItemButton
                selected={isActive('/admin/filter-switches')}
                onClick={() => {
                  navigate('/admin/filter-switches');
                  setMobileOpen(false);
                }}
                sx={{
                  minHeight: 48,
                  '&.Mui-selected': {
                    backgroundColor: 'action.selected',
                    borderRight: '3px solid',
                    borderColor: 'primary.main',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <TuneIcon />
                </ListItemIcon>
                <ListItemText
                  primary="מתגי סינון"
                  primaryTypographyProps={{
                    fontSize: '0.95rem',
                    fontWeight: isActive('/admin/filter-switches') ? 600 : 400,
                  }}
                />
              </ListItemButton>
            </ListItem>
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
          backgroundColor: 'background.paper',
          color: 'text.primary',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          borderBottom: '1px solid',
          borderColor: 'divider',
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
                <ListItemText>עריכת פרופיל</ListItemText>
              </MenuItem>
              <MenuItem onClick={() => { navigate('/profile/edit'); handleMenuClose(); }}>
                <ListItemIcon>
                  <SettingsIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>הגדרות</ListItemText>
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}>
                <ListItemIcon>
                  <LogoutIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>התנתק</ListItemText>
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
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          backgroundColor: 'background.default',
          minHeight: '100vh',
        }}
      >
        <Toolbar sx={{ minHeight: '64px !important' }} />
        {children}
      </Box>
    </Box>
  );
};

export default AdminLayout;
