export default function SimplePage() {
  const containerStyle = {
    maxWidth: '800px',
    margin: '20px auto',
    background: 'white',
    padding: '30px',
    borderRadius: '8px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
    fontFamily: 'system-ui, -apple-system, sans-serif'
  };

  const successStyle = {
    background: '#dcfce7',
    border: '1px solid #bbf7d0',
    color: '#166534',
    padding: '15px',
    borderRadius: '6px',
    marginBottom: '20px'
  };

  const infoStyle = {
    background: '#dbeafe',
    border: '1px solid #93c5fd',
    color: '#1e40af',
    padding: '15px',
    borderRadius: '6px',
    marginBottom: '20px'
  };

  const linkStyle = {
    display: 'inline-block',
    color: '#2563eb',
    textDecoration: 'none',
    padding: '8px 16px',
    background: '#eff6ff',
    borderRadius: '4px',
    margin: '5px'
  };

  return (
    <div style={containerStyle}>
      <h1>🎯 Super Over Alchemy - Simple Test</h1>

      <div style={successStyle}>
        ✅ Simple page loaded successfully using inline styles!
      </div>

      <div style={infoStyle}>
        ℹ️ This page uses inline CSS to test if the fundamental Next.js routing is working.
      </div>

      <h2>Navigation Test</h2>
      <div>
        <a href="/test" style={linkStyle}>Go to Test Page</a>
        <a href="/dashboard" style={linkStyle}>Go to Dashboard</a>
        <a href="/files" style={linkStyle}>Go to Files</a>
      </div>

      <h2>System Info</h2>
      <ul>
        <li>Framework: Next.js 15</li>
        <li>Runtime: React 19</li>
        <li>Styling: Inline CSS</li>
        <li>Components: Server Component</li>
      </ul>

      <p><small>Created at: {new Date().toISOString()}</small></p>
    </div>
  );
}