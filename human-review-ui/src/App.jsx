import React, { useState, useEffect } from 'react'
import { 
  Bell, 
  FileText, 
  CheckCircle, 
  XCircle, 
  AlertTriangle, 
  MessageSquare,
  ChevronRight,
  ShieldCheck,
  Search,
  LayoutDashboard,
  UploadCloud,
  FilePlus,
  Loader2,
  ChevronDown,
  ChevronUp,
  FileBox
} from 'lucide-react'

const API_BASE = "http://localhost:8000/api"

function App() {
  const [notifications, setNotifications] = useState([])
  const [selectedInvoice, setSelectedInvoice] = useState(null)
  const [loading, setLoading] = useState(true)
  const [comment, setComment] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState("review") // "review" or "upload"

  useEffect(() => {
    fetchNotifications()
  }, [])

  const fetchNotifications = async () => {
    try {
      const res = await fetch(`${API_BASE}/notifications`)
      const data = await res.json()
      setNotifications(data.notifications || [])
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch notifications", err)
      setLoading(false)
    }
  }

  const fetchInvoiceDetail = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/invoices/${id}`)
      const data = await res.json()
      setSelectedInvoice(data)
      setComment("")
    } catch (err) {
      console.error("Failed to fetch invoice", err)
    }
  }

  const handleDecision = async (status) => {
    if (!selectedInvoice) return
    setSubmitting(true)
    try {
      const res = await fetch(`${API_BASE}/invoices/${selectedInvoice.id}/review`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status,
          human_comment: comment
        })
      })
      if (res.ok) {
        // Success
        setSelectedInvoice(null)
        fetchNotifications()
      }
    } catch (err) {
      console.error("Decision failed", err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpload = async (file) => {
    setSubmitting(true)
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const res = await fetch(`${API_BASE}/invoices/upload`, {
        method: 'POST',
        body: formData
      })
      if (res.ok) {
        setActiveTab("review")
        fetchNotifications()
      }
    } catch (err) {
      console.error("Upload failed", err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <aside className="sidebar glass-panel">
        <div className="sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '1rem' }}>
            <div style={{ background: 'var(--primary)', padding: '0.4rem', borderRadius: '0.5rem' }}>
              <LayoutDashboard size={20} color="white" />
            </div>
            <h2 style={{ fontSize: '1.2rem' }}>AI Auditor</h2>
          </div>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', top: '10px', left: '10px', color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search invoices..." 
              style={{ width: '100%', padding: '0.5rem 0.5rem 0.5rem 2rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: 'white', borderRadius: '0.5rem' }} 
            />
          </div>
        </div>

        <div className="invoice-list">
          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
          ) : notifications.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No pending reviews</div>
          ) : (
            notifications.map(notif => (
              <div 
                key={notif.id} 
                className={`invoice-item glass-panel ${selectedInvoice?.id === notif.invoice_id ? 'active' : ''}`}
                onClick={() => fetchInvoiceDetail(notif.invoice_id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Inv #{notif.invoice_id}</span>
                  <span className="badge badge-review">Requires Review</span>
                </div>
                <div style={{ fontSize: '0.9rem', marginBottom: '0.5rem', fontWeight: 500 }}>
                  {notif.message.substring(0, 60)}...
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {new Date(notif.created_at).toLocaleDateString()}
                </div>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-view glass-panel">
        <div className="tabs" style={{ marginTop: '1.5rem' }}>
          <button 
            className={`tab-btn ${activeTab === 'review' ? 'active' : ''}`}
            onClick={() => setActiveTab('review')}
          >
            Pending Review
          </button>
          <button 
            className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
          >
            Upload Invoice
          </button>
        </div>

        {activeTab === 'upload' ? (
          <UploadView onUpload={handleUpload} submitting={submitting} />
        ) : selectedInvoice ? (
          <>
            <div className="header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Invoices</span>
                <ChevronRight size={14} color="var(--text-muted)" />
                <span style={{ fontWeight: 600 }}>{selectedInvoice.filename}</span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <div className={`confidence-gauge ${selectedInvoice.confidence_score > 0.8 ? 'high-conf' : selectedInvoice.confidence_score > 0.5 ? 'med-conf' : 'low-conf'}`}>
                  {Math.round(selectedInvoice.confidence_score * 100)}%
                </div>
              </div>
            </div>

            <div className="scroll-content">
              {/* Left Column: Details */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <section className="glass-panel" style={{ background: 'rgba(76, 201, 240, 0.05)' }}>
                   <div style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.6rem', color: 'var(--primary)', borderBottom: '1px solid var(--glass-border)' }}>
                    <ShieldCheck size={18} />
                    <h3 style={{ fontSize: '1rem' }}>AI Agent Reasoning</h3>
                  </div>
                  <div style={{ padding: '1.25rem' }}>
                    <p style={{ lineHeight: '1.6', color: '#cbd5e1', fontSize: '0.9rem' }}>
                      {selectedInvoice.human_review_notes || "No explanation provided by agent."}
                    </p>
                  </div>
                </section>

                <CollapsibleSection title="Invoice Details" icon={<FileText size={18} />} defaultOpen={true}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <DataField label="Supplier" value={selectedInvoice.extracted_data?.supplier_name} />
                    <DataField label="Invoice #" value={selectedInvoice.extracted_data?.invoice_number} />
                    <DataField label="Total TTC" value={selectedInvoice.extracted_data?.total_ttc ? `${selectedInvoice.extracted_data.total_ttc} ${selectedInvoice.extracted_data.currency}` : "N/A"} />
                    <DataField label="VAT Number" value={selectedInvoice.extracted_data?.vat_number} />
                    <DataField label="PO Number" value={selectedInvoice.extracted_data?.po_number || "None"} />
                    <DataField label="Date" value={selectedInvoice.extracted_data?.invoice_date} />
                    <DataField label="IBAN" value={selectedInvoice.extracted_data?.iban} />
                    <DataField label="BIC" value={selectedInvoice.extracted_data?.bic} />
                  </div>
                </CollapsibleSection>

                <CollapsibleSection title="Line Items" icon={<FileBox size={18} />}>
                  <div className="line-table-container">
                    <table className="line-table">
                      <thead>
                        <tr>
                          <th>Description</th>
                          <th>Qty</th>
                          <th>Price</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(selectedInvoice.extracted_data?.line_items || []).map((item, idx) => (
                          <tr key={idx}>
                            <td>{item.description}</td>
                            <td>{item.quantity}</td>
                            <td>{item.unit_price}</td>
                            <td style={{ fontWeight: 600 }}>{item.total}</td>
                          </tr>
                        ))}
                        {(!selectedInvoice.extracted_data?.line_items || selectedInvoice.extracted_data.line_items.length === 0) && (
                          <tr>
                            <td colSpan="4" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>No line items extracted</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </CollapsibleSection>

                <section className="glass-panel" style={{ padding: '0 0 1.25rem 0' }}>
                   <div style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.6rem', color: 'var(--danger)', borderBottom: '1px solid var(--glass-border)' }}>
                    <AlertTriangle size={18} />
                    <h3 style={{ fontSize: '1rem' }}>Validation Failures</h3>
                  </div>
                  <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {selectedInvoice.validation_results?.filter(r => !r.valid).map((r, i) => (
                      <div key={i} style={{ display: 'flex', gap: '0.5rem', padding: '0.75rem', background: 'rgba(249, 65, 68, 0.08)', borderRadius: '0.5rem', border: '1px solid rgba(249, 65, 68, 0.2)' }}>
                        <XCircle size={14} style={{ marginTop: '2px', color: 'var(--danger)' }} />
                        <span style={{ fontSize: '0.85rem' }}><strong>{r.field}:</strong> {r.message}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>

              {/* Right Column: Actions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                 <section className="glass-panel" style={{ padding: '1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
                    <MessageSquare size={18} />
                    <h3 style={{ fontSize: '1rem' }}>Internal Comments</h3>
                  </div>
                  <div className="form-group">
                    <textarea 
                      placeholder="Add a note to the permanent record..." 
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                    ></textarea>
                  </div>
                  <div className="btn-group">
                    <button className="btn-reject" onClick={() => handleDecision('rejected')}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}>
                        <XCircle size={16} /> Confirm Reject
                      </div>
                    </button>
                    <button className="btn-approve" onClick={() => handleDecision('validated')}>
                       <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}>
                        <CheckCircle size={16} /> Override & Approve
                      </div>
                    </button>
                  </div>
                </section>

                <section style={{ textAlign: 'center', opacity: 0.6 }}>
                   <p style={{ fontSize: '0.8rem' }}>Original document: <a href={selectedInvoice.image_url} target="_blank" style={{ color: 'var(--primary)' }}>View PDF</a></p>
                </section>
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: 0.5 }}>
            <AlertTriangle size={48} style={{ marginBottom: '1rem' }} />
            <p>Select an invoice to start the review process</p>
          </div>
        )}
      </main>
    </div>
  )
}

function CollapsibleSection({ title, icon, defaultOpen = false, children }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  return (
    <section className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
      <div className="collapsible-header" onClick={() => setIsOpen(!isOpen)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          {icon}
          <h3 style={{ fontSize: '1rem' }}>{title}</h3>
        </div>
        {isOpen ? <ChevronUp size={18} color="var(--text-muted)" /> : <ChevronDown size={18} color="var(--text-muted)" />}
      </div>
      <div className="collapsible-content" style={{ maxHeight: isOpen ? '2000px' : '0', opacity: isOpen ? 1 : 0, padding: isOpen ? '0 1.25rem 1.25rem' : '0 1.25rem' }}>
        {children}
      </div>
    </section>
  )
}

function UploadView({ onUpload, submitting }) {
  const [dragActive, setDragActive] = useState(false)

  const handleFile = (e) => {
    const file = e.target.files?.[0] || e.dataTransfer?.files?.[0]
    if (file) onUpload(file)
  }

  return (
    <div style={{ padding: '3rem', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
      <div 
        className={`upload-zone ${dragActive ? 'active' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => { e.preventDefault(); setDragActive(false); handleFile(e); }}
        onClick={() => document.getElementById('fileInput').click()}
      >
        <input 
          id="fileInput"
          type="file" 
          style={{ display: 'none' }} 
          onChange={handleFile}
        />
        {submitting ? (
          <div style={{ padding: '2rem' }}>
            <Loader2 className="spinner" size={48} style={{ color: 'var(--primary)', marginBottom: '1rem' }} />
            <h3>Processing Invoice...</h3>
            <p>The AI Agents are extracting data and validating against the ERP.</p>
          </div>
        ) : (
          <>
            <UploadCloud size={64} color="var(--primary)" />
            <h3>Click or Drag Invoice</h3>
            <p>Supports PDF, PNG, JPG (Max 10MB)</p>
          </>
        )}
      </div>
      
      <div style={{ marginTop: '2rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
            <ShieldCheck size={16} color="var(--primary)" /> Automated Audit
          </h4>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}> Every upload is programmatically audited for math and completeness.</p>
        </div>
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
            <FilePlus size={16} color="var(--primary)" /> Smart Routing
          </h4>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Failed validations are automatically routed to your review queue.</p>
        </div>
      </div>
    </div>
  )
}

function DataField({ label, value }) {
  return (
    <div style={{ marginBottom: '0.5rem' }}>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '0.9rem', fontWeight: 500 }}>{value || <span style={{ color: 'var(--danger)' }}>Missing</span>}</div>
    </div>
  )
}

export default App
