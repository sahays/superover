export default function TestPage() {
  return (
    <div style={{ minHeight: '100vh', background: 'white', padding: '32px' }}>
      <div style={{ maxWidth: '1024px', margin: '0 auto' }}>
        <h1 style={{ fontSize: '36px', fontWeight: 'bold', color: '#111827', marginBottom: '32px' }}>
          Super Over Alchemy - Test Page
        </h1>

        <div style={{ background: '#f9fafb', borderRadius: '8px', padding: '24px', marginBottom: '32px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: '600', color: '#374151', marginBottom: '16px' }}>
            ✅ Test Page Loaded Successfully
          </h2>
          <p style={{ color: '#6b7280' }}>
            This is a simple test page to verify that the Next.js application is working properly.
            Using inline styles to avoid CSS loading issues.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
          <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '24px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1e3a8a', marginBottom: '8px' }}>Frontend Status</h3>
            <p style={{ color: '#1d4ed8' }}>Next.js 15 + React 19 + TypeScript</p>
          </div>

          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '24px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#14532d', marginBottom: '8px' }}>Styling</h3>
            <p style={{ color: '#15803d' }}>Inline CSS (No Tailwind dependency)</p>
          </div>
        </div>

        <div style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px' }}>
          <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#111827', marginBottom: '16px' }}>Quick Navigation Test</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <a
              href="/simple"
              style={{
                display: 'block',
                padding: '8px 16px',
                fontSize: '14px',
                color: '#2563eb',
                background: '#eff6ff',
                borderRadius: '4px',
                textDecoration: 'none'
              }}
            >
              → Go to Simple Page
            </a>
            <a
              href="/dashboard"
              style={{
                display: 'block',
                padding: '8px 16px',
                fontSize: '14px',
                color: '#2563eb',
                background: '#eff6ff',
                borderRadius: '4px',
                textDecoration: 'none'
              }}
            >
              → Go to Dashboard
            </a>
            <a
              href="/files"
              style={{
                display: 'block',
                padding: '8px 16px',
                fontSize: '14px',
                color: '#2563eb',
                background: '#eff6ff',
                borderRadius: '4px',
                textDecoration: 'none'
              }}
            >
              → Go to Files
            </a>
          </div>
        </div>

        <div style={{ marginTop: '32px', fontSize: '14px', color: '#6b7280' }}>
          Test page created at: {new Date().toLocaleString()}
        </div>
      </div>
    </div>
  );
}