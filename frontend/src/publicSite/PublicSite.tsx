import type { ReactNode } from 'react'

import { AppIcon } from '../system/AppIcon'
import { publicPages, type PublicPagePath } from './pages'
import './publicSite.css'

export function PublicLinks() {
  return (
    <nav aria-label="Merydio information">
      {publicPages.map((page) => (
        <a key={page.path} href={page.path}>
          {page.label}
        </a>
      ))}
    </nav>
  )
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <span>Merydio</span>
      <PublicLinks />
    </footer>
  )
}

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="public-shell">
      {children}
      <SiteFooter />
    </div>
  )
}

function PageBody({ path }: { path: PublicPagePath }) {
  switch (path) {
    case '/about':
      return (
        <>
          <p>
            Merydio is a web-based annual-leave planner for teams managing consultant leave. A
            workspace brings consultant records, leave years, job plans, entitlement calculations,
            requests and a shared calendar together.
          </p>
          <h2>How It Works</h2>
          <p>
            Workspace owners and admins configure consultant records and review leave requests.
            Linked members can request leave and see the information their workspace makes available
            to them. Approved bookings count as leave unless they are cancelled.
          </p>
          <h2>Calculation Boundaries</h2>
          <p>
            Results depend on the dates, job plans, leave policy and other details entered by the
            workspace. They support planning; they do not approve leave or replace an employer's
            policy, local checks or professional judgement. A workspace should confirm its policy
            interpretation before relying on a calculation for a real decision.
          </p>
        </>
      )
    case '/privacy':
      return (
        <>
          <p>
            This notice explains how Merydio handles account information and the records entered
            into its leave-planning workspaces. Contact us at{' '}
            <a href="mailto:contact@merydio.co.uk">contact@merydio.co.uk</a> with privacy questions.
          </p>
          <h2>Who Is Responsible?</h2>
          <p>
            Merydio manages accounts, the service and its hosting. Workspace owners decide which
            consultant details their teams enter and who can access them. An organisation using
            Merydio for its staff records must establish its own data-protection responsibilities
            and authorise that use; creating a workspace does not provide organisational approval.
          </p>
          <h2>Information We Handle</h2>
          <p>
            Accounts contain names, email addresses, password hashes and membership details.
            Workspaces can contain consultant names and post titles, job plans, leave years,
            entitlement inputs and results, leave bookings and optional notes. The service also
            records activity needed for security, audit, recovery and email delivery. Consultant
            details may be entered by a workspace owner or admin rather than by the consultant.
          </p>
          <h2>What We Use It For</h2>
          <p>
            We use account details to register and authenticate users, manage access, send
            verification and recovery messages, and respond to enquiries. Workspace information is
            used to calculate leave, display balances and calendars, process booking requests,
            notify the relevant people, and preserve an audit trail of changes. Security records
            help detect misuse and investigate incidents. We do not provide advertising or sell
            workspace data.
          </p>
          <h2>Reasons for Processing</h2>
          <p>
            We process account, contact and security information to provide and protect the service,
            respond to enquiries and maintain a record of important actions. Our basis for those
            activities is our legitimate interest in operating a usable and secure service, except
            where a legal obligation applies. The organisation responsible for staff records must
            determine and explain its own lawful basis for putting those records into Merydio.
            Publicly available names or posts do not make leave dates, job plans or account details
            public information.
          </p>
          <h2>Access and Sharing</h2>
          <p>
            Access is scoped to a workspace. Owners and admins can manage its consultant records;
            linked members can access their own records and the shared team calendar according to
            their role. Other workspaces do not receive that access. The operator may access data
            when needed to operate, secure, back up or support the service.
          </p>
          <p>
            Cloudflare carries public website traffic and forwards messages sent to the contact
            address. Resend sends account and booking emails; Google receives forwarded contact
            messages. These providers process the information necessary for their services. Some
            processing may occur outside the UK. Their published transfer information is available
            from <a href="https://www.cloudflare.com/cloudflare-customer-dpa/">Cloudflare</a>,{' '}
            <a href="https://resend.com/legal/dpa">Resend</a> and{' '}
            <a href="https://policies.google.com/privacy/frameworks?hl=en-GB">Google</a>. Contact us
            for details relevant to your information.
          </p>
          <h2>Cookies and Security</h2>
          <p>
            Essential cookies maintain a signed-in session and protect changes against forged
            requests. The service does not need an advertising cookie to provide its workspace.
            Access controls, HTTPS, audit records and restricted backups are used to protect data;
            no system can promise absolute security.
          </p>
          <h2>Keeping and Removing Data</h2>
          <p>
            Workspace records remain while the workspace is active. Closing a workspace stops normal
            access and gives its owner 30 days to recover it. After that, permanent removal of the
            workspace and its audit history requires a separate operator action; it does not happen
            automatically on day 30.
          </p>
          <p>
            Database backups are made daily and verified by restoring them. Backups older than about
            30 days are removed only after a new backup has been verified, so a failed run can
            extend that period. Copies made before workspace removal can remain until their backups
            are removed. Global accounts and security records do not currently have an automatic
            deletion schedule. We keep them while needed to operate and protect the service or
            investigate an issue, and review removal requests individually rather than automatically
            purging accounts.
          </p>
          <h2>Your Choices and Rights</h2>
          <p>
            You can ask about access, correction, deletion, restriction, portability or objection
            where the relevant data-protection right applies. Email{' '}
            <a href="mailto:contact@merydio.co.uk">contact@merydio.co.uk</a>; we may need to verify
            your identity and coordinate with the workspace organisation. You can also complain to
            the <a href="https://ico.org.uk/make-a-complaint/">ICO</a>. Leave calculations support
            human decisions; the service does not itself approve leave through a solely automated
            decision.
          </p>
        </>
      )
    case '/terms':
      return (
        <>
          <p>
            These terms cover use of Merydio. They do not replace an organisation's approval or any
            data-processing agreement needed for its staff records.
          </p>
          <h2>Accounts and Workspaces</h2>
          <p>
            Use your own account and keep its access details secure. Workspace owners control
            membership and are responsible for inviting appropriate people, assigning roles and
            ensuring the consultant information entered by their team is accurate and authorised. Do
            not use another person's account or try to access a workspace that is not yours.
          </p>
          <h2>Appropriate Information</h2>
          <p>
            Enter information relevant to leave planning only. Do not put diagnoses, medical
            histories, patient information or other unnecessary sensitive details in names, notes or
            booking records. If you manage staff information for an organisation, make sure you have
            its permission and have met its information-governance requirements before adding real
            records.
          </p>
          <h2>Calculations and Decisions</h2>
          <p>
            The planner uses the configuration and policy rules available in the workspace. Owners
            and admins must check inputs, applicable policy and resulting calculations before using
            them for an employment decision. A booking request is not approved leave until an
            authorised owner or admin approves it.
          </p>
          <h2>Availability and Changes</h2>
          <p>
            The service may need maintenance or updates and can become temporarily unavailable. If
            you encounter an incorrect calculation, lost access or a security concern, contact us
            with enough detail to investigate, but do not send unnecessary personal information by
            email. No response time or uninterrupted-availability promise is made here.
          </p>
          <h2>Closing a Workspace</h2>
          <p>
            An owner may close a workspace and recover it within 30 days. Closing it does not
            immediately erase its records. See <a href="/privacy">Privacy</a> for the current
            deletion and backup position. Contact us if you need help with access or data requests.
          </p>
        </>
      )
    case '/contact':
      return (
        <p>
          Questions, feedback or need help? Email{' '}
          <a href="mailto:contact@merydio.co.uk">contact@merydio.co.uk</a>. Please do not include
          passwords or sensitive staff information.
        </p>
      )
  }
}

export function PublicInformationPage({ path }: { path: PublicPagePath }) {
  const title = publicPages.find((page) => page.path === path)!.label

  return (
    <div className="public-document-page">
      <header className="public-document-header">
        <a href="/" aria-label="Merydio Leave Planner home">
          <AppIcon name="calendar" />
          <span>Merydio</span>
        </a>
        <a className="public-document-return" href="/">
          Back To App
        </a>
      </header>
      <main className="public-document" id="main-content">
        <span className="section-label">Merydio Leave Planner</span>
        <h1>{title}</h1>
        <PageBody path={path} />
      </main>
      <SiteFooter />
    </div>
  )
}
