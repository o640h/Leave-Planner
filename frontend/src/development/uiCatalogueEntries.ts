export type CatalogueGroup = 'Account' | 'Application States' | 'Workspace'

export type UiCatalogueEntry = {
  path: string
  title: string
  description: string
  group: CatalogueGroup
  usesLiveData?: boolean
}

export const uiCatalogueEntries: UiCatalogueEntry[] = [
  {
    path: '/ui/login',
    title: 'Sign In',
    description: 'Standard account sign-in screen.',
    group: 'Account',
  },
  {
    path: '/ui/register',
    title: 'Create Account',
    description: 'Open-registration account creation.',
    group: 'Account',
  },
  {
    path: '/ui/forgot-password',
    title: 'Forgot Password',
    description: 'Password-reset email request.',
    group: 'Account',
  },
  {
    path: '/ui/reset-password',
    title: 'Reset Password',
    description: 'New-password form opened from an email link.',
    group: 'Account',
  },
  {
    path: '/ui/verify-email',
    title: 'Verify Email',
    description: 'Account-creation email confirmation.',
    group: 'Account',
  },
  {
    path: '/ui/confirm-email',
    title: 'Confirm New Email',
    description: 'Email-change confirmation link.',
    group: 'Account',
  },
  {
    path: '/ui/change-email',
    title: 'Change Email',
    description: 'Authenticated email-change form.',
    group: 'Account',
  },
  {
    path: '/ui/account',
    title: 'Account',
    description: 'Signed-in identity and account security actions.',
    group: 'Account',
  },
  {
    path: '/ui/connecting',
    title: 'Connecting',
    description: 'Initial server connection state.',
    group: 'Application States',
  },
  {
    path: '/ui/server-unavailable',
    title: 'Server Unavailable',
    description: 'Connection failure and retry state.',
    group: 'Application States',
  },
  {
    path: '/ui/access-denied',
    title: 'Access Denied',
    description: 'Signed-in account without selected-workspace access.',
    group: 'Application States',
  },
  {
    path: '/ui/no-workspace',
    title: 'No Workspace',
    description: 'New-account onboarding state.',
    group: 'Application States',
  },
  {
    path: '/ui/create-workspace',
    title: 'Create Workspace',
    description: 'Blank-workspace creation dialog over onboarding.',
    group: 'Application States',
  },
  {
    path: '/ui/workspace-selection',
    title: 'Workspace Selection',
    description: 'Required workspace-selection state.',
    group: 'Application States',
  },
  {
    path: '/ui/member-workspace',
    title: 'Member Workspace',
    description: 'Temporary Member holding state.',
    group: 'Application States',
  },
  {
    path: '/ui/consultants',
    title: 'Consultants',
    description: 'Consultant directory and selected-consultant workspace.',
    group: 'Workspace',
    usesLiveData: true,
  },
  {
    path: '/ui/planning',
    title: 'Planning',
    description: 'Shared planning calendar.',
    group: 'Workspace',
    usesLiveData: true,
  },
  {
    path: '/ui/settings/workspace',
    title: 'Workspace Settings',
    description: 'Workspace and membership administration.',
    group: 'Workspace',
    usesLiveData: true,
  },
  {
    path: '/ui/settings/public-holidays',
    title: 'Public Holiday Settings',
    description: 'Holiday source and Trust corrections.',
    group: 'Workspace',
    usesLiveData: true,
  },
  {
    path: '/ui/settings/policy',
    title: 'Policy & Guidance Settings',
    description: 'Read-only annual leave reference documents.',
    group: 'Workspace',
    usesLiveData: true,
  },
]
