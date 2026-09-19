import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard, Users, CheckSquare, Sparkles, Bot, History, Settings,
  AlertTriangle, CheckCircle2, XCircle, RefreshCw, Download, Plus, Search,
  Clock, ShieldAlert, ArrowRight, FileSpreadsheet, UserCheck, Play, BarChart2, PieChart as PieIcon,
  User, Mail, MapPin, Briefcase, Star, FileText
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
  PieChart, Pie, Cell
} from 'recharts';

// In production (Vercel), VITE_API_URL points to Railway backend.
// In development, it's empty (proxy handles /api → localhost:8000).
const API_BASE = import.meta.env.VITE_API_URL || '';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [history, setHistory] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Modals
  const [showAddEmp, setShowAddEmp] = useState(false);
  const [showAddTask, setShowAddTask] = useState(false);
  const [selectedCycle, setSelectedCycle] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState(null); // Employee Profile Modal state

  // Form states
  const [newEmp, setNewEmp] = useState({
    name: '', email: '', skills: 'Python:3,FastAPI:3', location: 'Remote', working_hours_per_week: 40
  });
  const [newTask, setNewTask] = useState({
    title: '', description: '', required_skills: 'Python:3', location: 'Remote',
    estimated_hours: 10, priority: 'Medium', urgency: 'Medium', deadline: new Date(Date.now() + 86400000*3).toISOString().slice(0,16)
  });

  // Assistant state
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', text: 'Hello! I am your WorkWise AI Assistant. I can help analyze employee capacity, resolve at-risk tasks, match candidates, or register employees and tasks in natural language.' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [ollamaStatus, setOllamaStatus] = useState({ online: false, model: 'gemma3:4b', status: 'checking' });
  const [isGenerating, setIsGenerating] = useState(false);

  // Initial Load
  useEffect(() => {
    fetchDashboard();
    fetchEmployees();
    fetchTasks();
    fetchRecommendations();
    fetchHistory();
    fetchSettings();
    fetchOllamaStatus();
  }, []);

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard`);
      if (res.ok) setDashboard(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchEmployees = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/employees`);
      if (res.ok) setEmployees(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tasks`);
      if (res.ok) setTasks(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchRecommendations = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/recommendations`);
      if (res.ok) {
        const data = await res.json();
        setRecommendations(data);
        if (data.length > 0 && !selectedCycle) {
          setSelectedCycle(data[0]);
        }
      }
    } catch (e) { console.error(e); }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/history`);
      if (res.ok) setHistory(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`);
      if (res.ok) setSettings(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchOllamaStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/assistant/status`);
      if (res.ok) {
        const data = await res.json();
        setOllamaStatus(data);
      }
    } catch (e) {
      setOllamaStatus({ online: false, model: 'gemma3:4b', status: 'unreachable' });
    }
  };

  const refreshAll = () => {
    fetchDashboard();
    fetchEmployees();
    fetchTasks();
    fetchRecommendations();
    fetchHistory();
    fetchSettings();
    fetchOllamaStatus();
  };

  const openEmployeeProfile = async (empId) => {
    try {
      const res = await fetch(`/api/employees/${empId}/profile`);
      if (res.ok) {
        setSelectedProfile(await res.json());
      }
    } catch (e) { alert(e.message); }
  };

  // Handlers
  const handleCreateEmployee = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/employees`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newEmp)
      });
      if (res.ok) {
        setShowAddEmp(false);
        setNewEmp({ name: '', email: '', skills: 'Python:3,FastAPI:3', location: 'Remote', working_hours_per_week: 40 });
        refreshAll();
      } else {
        const err = await res.json();
        alert('Error: ' + (err.detail || 'Failed to create employee'));
      }
    } catch (e) { alert(e.message); }
    setLoading(false);
  };

  const handleCreateTask = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTask)
      });
      if (res.ok) {
        setShowAddTask(false);
        setNewTask({
          title: '', description: '', required_skills: 'Python:3', location: 'Remote',
          estimated_hours: 10, priority: 'Medium', urgency: 'Medium', deadline: new Date(Date.now() + 86400000*3).toISOString().slice(0,16)
        });
        refreshAll();
      } else {
        const err = await res.json();
        alert('Error: ' + (err.detail || 'Failed to create task'));
      }
    } catch (e) { alert(e.message); }
    setLoading(false);
  };

  const handleToggleEmployeeAvailability = async (empId, currentVal) => {
    try {
      const res = await fetch(`/api/employees/${empId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_available: !currentVal })
      });
      if (res.ok) {
        refreshAll();
        if (selectedProfile && selectedProfile.employee.id === empId) {
          openEmployeeProfile(empId);
        }
      }
    } catch (e) { console.error(e); }
  };

  const handleTriggerRecommend = async (taskId) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tasks/${taskId}/recommend`, { method: 'POST' });
      if (res.ok) {
        const cycle = await res.json();
        setSelectedCycle(cycle);
        setActiveTab('recommendations');
        refreshAll();
      }
    } catch (e) { alert(e.message); }
    setLoading(false);
  };

  const handleApproveCandidate = async (cycleId, empId) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/recommendations/${cycleId}/approve?candidate_employee_id=${empId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actor: 'Manager', reason: 'Manager approval' })
      });
      if (res.ok) {
        refreshAll();
      } else {
        const err = await res.json();
        alert('Approval failed: ' + (err.detail || 'Unknown error'));
      }
    } catch (e) { alert(e.message); }
    setLoading(false);
  };

  const handleRejectCandidate = async (cycleId, empId) => {
    const reason = prompt('Reason for rejection:', 'Not a good fit for this task');
    if (reason === null) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/recommendations/${cycleId}/reject?candidate_employee_id=${empId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actor: 'Manager', reason })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedCycle(updated);
        refreshAll();
      }
    } catch (e) { alert(e.message); }
    setLoading(false);
  };

  const handleCompleteTask = async (taskId) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tasks/${taskId}/complete`, { method: 'POST' });
      if (res.ok) {
        refreshAll();
        if (selectedProfile) openEmployeeProfile(selectedProfile.employee.id);
      }
    } catch (e) { alert(e.message); }
    setLoading(false);
  };

  const handleRebuildExcel = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/history/rebuild-excel`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        alert(`Excel shared log rebuilt successfully! ${data.rows_written} rows written to ${data.excel_path}`);
        fetchSettings();
      }
    } catch (e) { alert(e.message); }
    setLoading(false);
  };

  const handleSendMessage = async (msgText) => {
    const txt = msgText || chatInput;
    if (!txt.trim() || isGenerating) return;

    const newMsgs = [...chatMessages, { role: 'user', text: txt }];
    setChatMessages(newMsgs);
    if (!msgText) setChatInput('');
    setIsGenerating(true);

    try {
      const res = await fetch(`${API_BASE}/api/assistant/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: txt, session_id: 'default' })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages([...newMsgs, { role: 'assistant', text: data.reply, model: data.model_name }]);
        refreshAll();
      } else {
        setChatMessages([...newMsgs, { role: 'assistant', text: 'Error: Failed to obtain response from assistant.' }]);
      }
    } catch (e) {
      setChatMessages([...newMsgs, { role: 'assistant', text: 'Error communicating with assistant backend.' }]);
    }
    setIsGenerating(false);
  };

  // Recharts Chart Data Preparation
  const employeeWorkloadChartData = employees.map(emp => ({
    name: emp.name,
    'Current Workload (h)': emp.current_workload,
    'Remaining Headroom (h)': emp.remaining_capacity,
    capacity: emp.working_hours_per_week
  }));

  const taskStatusChartData = dashboard ? [
    { name: 'Pending', value: dashboard.pending_tasks, color: '#f59e0b' },
    { name: 'Active / Assigned', value: dashboard.active_tasks, color: '#2563eb' },
    { name: 'Completed', value: dashboard.completed_tasks, color: '#16a34a' },
    { name: 'At-Risk', value: dashboard.at_risk_tasks, color: '#dc2626' }
  ].filter(d => d.value > 0) : [];

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <Sparkles size={24} />
          <span>WorkWise AI</span>
        </div>
        <ul className="nav-list">
          <li className="nav-item">
            <button className={activeTab === 'dashboard' ? 'active' : ''} onClick={() => setActiveTab('dashboard')}>
              <LayoutDashboard size={18} /> Dashboard
            </button>
          </li>
          <li className="nav-item">
            <button className={activeTab === 'employees' ? 'active' : ''} onClick={() => setActiveTab('employees')}>
              <Users size={18} /> Employees
            </button>
          </li>
          <li className="nav-item">
            <button className={activeTab === 'tasks' ? 'active' : ''} onClick={() => setActiveTab('tasks')}>
              <CheckSquare size={18} /> Tasks
            </button>
          </li>
          <li className="nav-item">
            <button className={activeTab === 'recommendations' ? 'active' : ''} onClick={() => setActiveTab('recommendations')}>
              <Sparkles size={18} /> Recommendations
              {recommendations.length > 0 && <span className="badge badge-warning" style={{marginLeft:'auto'}}>{recommendations.length}</span>}
            </button>
          </li>
          <li className="nav-item">
            <button className={activeTab === 'assistant' ? 'active' : ''} onClick={() => setActiveTab('assistant')}>
              <Bot size={18} /> AI Assistant
            </button>
          </li>
          <li className="nav-item">
            <button className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>
              <History size={18} /> Audit History
            </button>
          </li>
          <li className="nav-item">
            <button className={activeTab === 'settings' ? 'active' : ''} onClick={() => setActiveTab('settings')}>
              <Settings size={18} /> Settings
            </button>
          </li>
        </ul>
        <div className="sidebar-footer">
          WorkWise AI v1.0 • mAI-04 Hackathon
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="header-bar">
          <h1 className="header-title">
            {activeTab === 'dashboard' && 'Dashboard Overview & Recharts Analytics'}
            {activeTab === 'employees' && 'Employee Workforce Profiles & Capacities'}
            {activeTab === 'tasks' && 'Task Lifecycle & SLA Monitoring'}
            {activeTab === 'recommendations' && 'AI Allocation & Random Forest Scorer'}
            {activeTab === 'assistant' && 'WorkWise AI Conversational Assistant & Entity Extractor'}
            {activeTab === 'history' && 'Audit History & Shared Excel Workbook Log'}
            {activeTab === 'settings' && 'System Configuration & Shared Excel Sync'}
          </h1>

          <div className="header-actions">
            {settings && (
              <div className={`sync-badge ${settings.excel_sync_status === 'OK' ? 'ok' : 'failed'}`}>
                <FileSpreadsheet size={16} />
                <span>Excel Sync: <strong>{settings.excel_sync_status}</strong></span>
              </div>
            )}

            <button className="btn btn-secondary btn-sm" onClick={refreshAll}>
              <RefreshCw size={14} /> Refresh
            </button>

            {activeTab === 'employees' && (
              <button className="btn btn-primary btn-sm" onClick={() => setShowAddEmp(true)}>
                <Plus size={14} /> Add Employee
              </button>
            )}

            {activeTab === 'tasks' && (
              <button className="btn btn-primary btn-sm" onClick={() => setShowAddTask(true)}>
                <Plus size={14} /> Create Task
              </button>
            )}
          </div>
        </header>

        <div className="content-body">
          {/* DASHBOARD TAB */}
          {activeTab === 'dashboard' && dashboard && (
            <div>
              {/* Metrics Grid */}
              <div className="grid-metrics">
                <div className="metric-card">
                  <div className="metric-label">Total / Active Workforce</div>
                  <div className="metric-value">{dashboard.available_employees} / {dashboard.total_employees}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Pending / Active Tasks</div>
                  <div className="metric-value">{dashboard.pending_tasks} / {dashboard.active_tasks}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Completed Tasks</div>
                  <div className="metric-value" style={{color: 'var(--success)'}}>{dashboard.completed_tasks}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">At-Risk Tasks</div>
                  <div className="metric-value" style={{color: dashboard.at_risk_tasks > 0 ? 'var(--danger)' : 'inherit'}}>
                    {dashboard.at_risk_tasks}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Workforce Utilization</div>
                  <div className="metric-value">{dashboard.avg_capacity_utilization}%</div>
                </div>
              </div>

              {/* RECHARTS ANALYTICS SECTION */}
              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:24, marginBottom:24}}>
                <div className="card">
                  <div className="card-title">
                    <BarChart2 size={20} /> Workforce Workload & Capacity Breakdown (Recharts)
                  </div>
                  {employeeWorkloadChartData.length === 0 ? (
                    <p style={{color:'var(--text-muted)'}}>No employee capacity data available.</p>
                  ) : (
                    <div style={{width:'100%', height:260}}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={employeeWorkloadChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                          <YAxis stroke="#64748b" fontSize={12} />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="Current Workload (h)" fill="#2563eb" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="Remaining Headroom (h)" fill="#16a34a" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>

                <div className="card">
                  <div className="card-title">
                    <PieIcon size={20} /> Task Status & SLA Risk Distribution (Recharts)
                  </div>
                  {taskStatusChartData.length === 0 ? (
                    <p style={{color:'var(--text-muted)'}}>No active task distribution data.</p>
                  ) : (
                    <div style={{width:'100%', height:260, display:'flex', alignItems:'center', justifyContent:'center'}}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={taskStatusChartData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            outerRadius={80}
                            label={(entry) => `${entry.name}: ${entry.value}`}
                          >
                            {taskStatusChartData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>

              {/* Latest Completed Task Banner */}
              {dashboard.latest_completed_task && (
                <div className="card" style={{borderLeft: '4px solid var(--success)', backgroundColor: 'var(--success-bg)'}}>
                  <div className="card-title">
                    <UserCheck size={20} style={{color: 'var(--success)'}} /> Latest Completed Task
                  </div>
                  <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <div>
                      <h4 style={{fontSize:'1.1rem'}}>{dashboard.latest_completed_task.title}</h4>
                      <p style={{fontSize:'0.9rem', color:'var(--text-muted)'}}>
                        Completed by: <strong>{dashboard.latest_completed_task.completed_by_employee_name || 'Unassigned'}</strong> (Logged by {dashboard.latest_completed_task.completed_by_actor || 'Manager'})
                      </p>
                    </div>
                    <div style={{textAlign:'right'}}>
                      <div className="badge badge-success" style={{fontSize:'0.85rem'}}>
                        <Clock size={12} style={{marginRight:4}} /> Completed at {new Date(dashboard.latest_completed_task.completed_at).toLocaleString()}
                      </div>
                      <div style={{fontSize:'0.85rem', marginTop:4, color:'var(--text-muted)'}}>
                        Effort: {dashboard.latest_completed_task.estimated_hours}h
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* At-Risk Tasks Alert List */}
              {dashboard.at_risk_task_list.length > 0 && (
                <div className="card" style={{borderLeft: '4px solid var(--danger)', backgroundColor: 'var(--danger-bg)'}}>
                  <div className="card-title" style={{color: 'var(--danger)'}}>
                    <ShieldAlert size={20} /> Tasks Requiring Dynamic Reallocation ({dashboard.at_risk_task_list.length})
                  </div>
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Task Title</th>
                          <th>Priority</th>
                          <th>Assigned Employee</th>
                          <th>Reason</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.at_risk_task_list.map(t => (
                          <tr key={t.id}>
                            <td><strong>{t.title}</strong></td>
                            <td><span className="badge badge-danger">{t.priority}</span></td>
                            <td>{t.assigned_employee_name || 'Unassigned'}</td>
                            <td>{t.at_risk_reason}</td>
                            <td>
                              <button className="btn btn-primary btn-sm" onClick={() => handleTriggerRecommend(t.id)}>
                                <Sparkles size={12} /> Reallocate Now
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Recent Activity Table */}
              <div className="card">
                <div className="card-title"><History size={20} /> System Audit Trail</div>
                <div className="data-table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Timestamp</th>
                        <th>Event Type</th>
                        <th>Task / Employee</th>
                        <th>Trigger & Notes</th>
                        <th>Actor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboard.recent_activity.map(ev => (
                        <tr key={ev.event_id}>
                          <td><small>{new Date(ev.timestamp).toLocaleTimeString()}</small></td>
                          <td>
                            <span className={`badge ${ev.event_type.includes('approved') ? 'badge-success' : ev.event_type.includes('rejected') ? 'badge-danger' : 'badge-info'}`}>
                              {ev.event_type}
                            </span>
                          </td>
                          <td>
                            {ev.task_title && <div><strong>Task:</strong> {ev.task_title}</div>}
                            {ev.employee_name && <div><small><strong>Emp:</strong> {ev.employee_name}</small></div>}
                          </td>
                          <td>{ev.notes || ev.trigger_reason}</td>
                          <td>{ev.actor}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* EMPLOYEES TAB */}
          {activeTab === 'employees' && (
            <div className="card">
              <div className="card-title"><Users size={20} /> Workforce Roster & Individual Profiles ({employees.length})</div>
              <div className="data-table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Name & Email</th>
                      <th>Location</th>
                      <th>Skills</th>
                      <th>Workload / Capacity</th>
                      <th>Status</th>
                      <th>Actions & Profile</th>
                    </tr>
                  </thead>
                  <tbody>
                    {employees.map(emp => (
                      <tr key={emp.id}>
                        <td>#{emp.id}</td>
                        <td>
                          <strong>{emp.name}</strong>
                          <div><small style={{color:'var(--text-muted)'}}>{emp.email}</small></div>
                        </td>
                        <td>{emp.location}</td>
                        <td>
                          <small style={{fontFamily:'monospace', background:'#f1f5f9', padding:'2px 6px', borderRadius:4}}>
                            {emp.skills}
                          </small>
                        </td>
                        <td>
                          <div><strong>{emp.current_workload}h</strong> / {emp.working_hours_per_week}h</div>
                          <small style={{color: emp.remaining_capacity < 5 ? 'var(--danger)' : 'var(--success)'}}>
                            Remaining: {emp.remaining_capacity}h
                          </small>
                        </td>
                        <td>
                          {emp.is_active ? (
                            <span className="badge badge-success">Active</span>
                          ) : (
                            <span className="badge badge-danger">Deactivated</span>
                          )}
                        </td>
                        <td>
                          <div style={{display:'flex', gap:6}}>
                            <button className="btn btn-secondary btn-sm" onClick={() => openEmployeeProfile(emp.id)}>
                              <User size={12} /> View Profile
                            </button>
                            <button
                              className={`btn btn-sm ${emp.is_available ? 'btn-secondary' : 'btn-primary'}`}
                              onClick={() => handleToggleEmployeeAvailability(emp.id, emp.is_available)}
                            >
                              {emp.is_available ? 'Unavailable' : 'Available'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TASKS TAB */}
          {activeTab === 'tasks' && (
            <div className="card">
              <div className="card-title"><CheckSquare size={20} /> Task Lifecycle ({tasks.length})</div>
              <div className="data-table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Task Details</th>
                      <th>Required Skills</th>
                      <th>Assigned To</th>
                      <th>Priority / Urgency</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map(t => (
                      <tr key={t.id}>
                        <td>#{t.id}</td>
                        <td>
                          <strong>{t.title}</strong>
                          <div><small style={{color:'var(--text-muted)'}}>Effort: {t.estimated_hours}h | Deadline: {t.deadline}</small></div>
                        </td>
                        <td>
                          <small style={{fontFamily:'monospace', background:'#f1f5f9', padding:'2px 6px', borderRadius:4}}>
                            {t.required_skills}
                          </small>
                        </td>
                        <td>{t.assigned_employee_name || <em>Unassigned</em>}</td>
                        <td>
                          <span className={`badge ${t.priority === 'High' || t.priority === 'Critical' ? 'badge-danger' : 'badge-info'}`}>
                            {t.priority}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${t.status === 'completed' ? 'badge-success' : t.status === 'assigned' ? 'badge-info' : t.status === 'at_risk' ? 'badge-danger' : 'badge-warning'}`}>
                            {t.status}
                          </span>
                        </td>
                        <td>
                          <div style={{display:'flex', gap:6}}>
                            {t.status !== 'completed' && (
                              <button className="btn btn-primary btn-sm" onClick={() => handleTriggerRecommend(t.id)}>
                                <Sparkles size={12} /> Match
                              </button>
                            )}
                            {t.status === 'assigned' && (
                              <button className="btn btn-success btn-sm" onClick={() => handleCompleteTask(t.id)}>
                                <CheckCircle2 size={12} /> Complete
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* RECOMMENDATIONS TAB */}
          {activeTab === 'recommendations' && (
            <div>
              {recommendations.length === 0 ? (
                <div className="card" style={{textAlign:'center', padding:'3rem'}}>
                  <Sparkles size={48} style={{color:'var(--primary)', marginBottom:12}} />
                  <h3>No Active Recommendation Cycles</h3>
                  <p style={{color:'var(--text-muted)', marginBottom:16}}>Select a task from the Tasks page to generate candidate recommendations.</p>
                  <button className="btn btn-primary" onClick={() => setActiveTab('tasks')}>
                    Go to Tasks Queue
                  </button>
                </div>
              ) : (
                <div style={{display:'grid', gridTemplateColumns:'300px 1fr', gap:24}}>
                  <div className="card">
                    <div className="card-title">Pending Cycles</div>
                    <div style={{display:'flex', flexDirection:'column', gap:8}}>
                      {recommendations.map(c => (
                        <button
                          key={c.cycle_id}
                          className={`btn ${selectedCycle && selectedCycle.cycle_id === c.cycle_id ? 'btn-primary' : 'btn-secondary'}`}
                          style={{justifyContent:'flex-start', textAlign:'left', width:'100%'}}
                          onClick={() => setSelectedCycle(c)}
                        >
                          <div>
                            <div><strong>Task #{c.task_id}</strong></div>
                            <small>{c.task_title}</small>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {selectedCycle && (
                    <div className="card">
                      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16}}>
                        <div>
                          <h2>Recommendation for Task #{selectedCycle.task_id}: {selectedCycle.task_title}</h2>
                          <p style={{fontSize:'0.85rem', color:'var(--text-muted)'}}>
                            Engine Model Version: <code>{selectedCycle.model_version}</code> | Trigger: {selectedCycle.trigger_reason}
                          </p>
                        </div>
                      </div>

                      {selectedCycle.no_qualifying_reason && (
                        <div className="card" style={{backgroundColor:'var(--warning-bg)', borderLeft:'4px solid var(--warning)'}}>
                          <div style={{display:'flex', gap:8, alignItems:'center', color:'var(--warning)', fontWeight:600}}>
                            <AlertTriangle size={18} /> Hard Constraint Warning
                          </div>
                          <p style={{fontSize:'0.9rem', marginTop:4, whiteSpace:'pre-wrap'}}>{selectedCycle.no_qualifying_reason}</p>
                        </div>
                      )}

                      <h3 style={{fontSize:'1.05rem', margin:'1.25rem 0 0.75rem'}}>Ranked Candidate Queue</h3>
                      <div className="data-table-container">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Rank</th>
                              <th>Candidate Employee</th>
                              <th>Random Forest Score</th>
                              <th>Hard Constraints</th>
                              <th>Workload / Capacity</th>
                              <th>Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedCycle.candidates.map(cand => (
                              <tr key={cand.employee_id} style={{opacity: cand.hard_constraints_passed ? 1 : 0.65}}>
                                <td><strong>#{cand.rank}</strong></td>
                                <td>
                                  <strong>{cand.employee_name}</strong>
                                </td>
                                <td>
                                  <div style={{fontFamily:'monospace', fontSize:'1rem', fontWeight:600, color:'var(--primary)'}}>
                                    {(cand.score * 100).toFixed(1)}%
                                  </div>
                                </td>
                                <td>
                                  {cand.hard_constraints_passed ? (
                                    <span className="badge badge-success"><CheckCircle2 size={12} style={{marginRight:4}} /> Passed</span>
                                  ) : (
                                    <span className="badge badge-danger"><XCircle size={12} style={{marginRight:4}} /> Failed</span>
                                  )}
                                  {!cand.hard_constraints_passed && (
                                    <div style={{fontSize:'0.75rem', color:'var(--danger)', marginTop:2}}>{cand.rejection_reason}</div>
                                  )}
                                </td>
                                <td>
                                  <small>{cand.employee_current_workload}h assigned (Headroom: {cand.employee_remaining_capacity}h)</small>
                                </td>
                                <td>
                                  {cand.hard_constraints_passed && cand.status === 'pending' && (
                                    <div style={{display:'flex', gap:6}}>
                                      <button className="btn btn-success btn-sm" onClick={() => handleApproveCandidate(selectedCycle.cycle_id, cand.employee_id)}>
                                        Approve
                                      </button>
                                      <button className="btn btn-danger btn-sm" onClick={() => handleRejectCandidate(selectedCycle.cycle_id, cand.employee_id)}>
                                        Reject
                                      </button>
                                    </div>
                                  )}
                                  {cand.status === 'rejected' && <span className="badge badge-danger">Rejected</span>}
                                  {cand.status === 'approved' && <span className="badge badge-success">Approved</span>}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* AI ASSISTANT TAB */}
          {activeTab === 'assistant' && (
            <div className="card">
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 16}}>
                <div className="card-title" style={{margin:0}}>
                  <Bot size={20} /> WorkWise AI Assistant
                </div>
                <div style={{display:'flex', alignItems:'center', gap: 10}}>
                  <div className={`model-badge ${ollamaStatus.online ? 'online' : 'offline'}`}>
                    <span style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: ollamaStatus.online ? '#16a34a' : '#dc2626',
                      display: 'inline-block'
                    }} />
                    <span>{ollamaStatus.online ? 'Ollama Online' : 'Offline'}</span>
                  </div>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      setChatMessages([
                        { role: 'assistant', text: 'Hello! I am your WorkWise AI Assistant. Ask me about workforce capacity, optimal task assignments, or ask me to add employees and tasks!' }
                      ]);
                    }}
                  >
                    Clear Chat
                  </button>
                </div>
              </div>

              <div className="chat-window">
                <div className="chat-messages">
                  {chatMessages.map((msg, idx) => (
                    <div key={idx} className={`message-bubble ${msg.role}`}>
                      {msg.text}
                    </div>
                  ))}
                  {isGenerating && (
                    <div className="message-bubble assistant thinking">
                      <span className="typing-dot"></span>
                      <span className="typing-dot"></span>
                      <span className="typing-dot"></span>
                      <span style={{marginLeft: 6}}>AI Assistant is generating response...</span>
                    </div>
                  )}
                </div>

                {/* Quick Prompt Suggestions */}
                <div className="prompt-suggestions">
                  <span style={{fontSize: '0.78rem', color: 'var(--text-muted)', alignSelf: 'center', marginRight: 4}}>Try asking:</span>
                  <button
                    className="prompt-chip"
                    onClick={() => handleSendMessage("Who has Python skills and available capacity?")}
                  >
                    🔍 Who has Python skills and capacity?
                  </button>
                  <button
                    className="prompt-chip"
                    onClick={() => handleSendMessage("Analyze current workforce bottlenecks and at-risk tasks")}
                  >
                    ⚠️ Analyze bottlenecks & at-risk tasks
                  </button>
                  <button
                    className="prompt-chip"
                    onClick={() => handleSendMessage("Give me an executive summary of our workforce utilization")}
                  >
                    📊 Executive workforce summary
                  </button>
                  <button
                    className="prompt-chip"
                    onClick={() => handleSendMessage("Add employee Sarah Connor, email sarah@skynet.com, skills Python:5, Machine Learning:4, location San Francisco, 40 hours")}
                  >
                    ➕ Register Sarah Connor (NLP)
                  </button>
                </div>

                <div className="chat-input-bar">
                  <input
                    type="text"
                    placeholder="Ask the AI Assistant anything about workforce, tasks, or allocation..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                    disabled={isGenerating}
                  />
                  <button
                    className="btn btn-primary"
                    onClick={() => handleSendMessage()}
                    disabled={isGenerating || !chatInput.trim()}
                  >
                    {isGenerating ? 'Thinking...' : 'Send'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* AUDIT HISTORY TAB */}
          {activeTab === 'history' && (
            <div className="card">
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16}}>
                <div className="card-title" style={{margin:0}}><History size={20} /> Complete Event History Log</div>
                <div style={{display:'flex', gap:8}}>
                  <a className="btn btn-secondary btn-sm" href={`${API_BASE}/api/history/export?format=csv`} download="allocation_history.csv">
                    <Download size={14} /> Export CSV
                  </a>
                  <a className="btn btn-primary btn-sm" href={`${API_BASE}/api/history/export?format=xlsx`} download="allocation_history.xlsx">
                    <FileSpreadsheet size={14} /> Download Shared Excel Workbook
                  </a>
                </div>
              </div>

              <div className="data-table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Event ID</th>
                      <th>Timestamp</th>
                      <th>Event Type</th>
                      <th>Task Title</th>
                      <th>Employee Name</th>
                      <th>Constraint Check</th>
                      <th>Actor</th>
                      <th>Notes / Trigger Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(ev => (
                      <tr key={ev.id}>
                        <td><small style={{fontFamily:'monospace'}}>{ev.event_id}</small></td>
                        <td><small>{new Date(ev.timestamp).toLocaleString()}</small></td>
                        <td>
                          <span className="badge badge-info">{ev.event_type}</span>
                        </td>
                        <td>{ev.task_title || '-'}</td>
                        <td>{ev.employee_name || '-'}</td>
                        <td>{ev.constraint_checks || '-'}</td>
                        <td>{ev.actor}</td>
                        <td><small>{ev.notes || ev.trigger_reason}</small></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* SETTINGS TAB */}
          {activeTab === 'settings' && settings && (
            <div>
              <div className="card">
                <div className="card-title"><FileSpreadsheet size={20} /> Shared Excel Allocation Log Mirror</div>
                <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:16}}>
                  <div>
                    <label style={{fontSize:'0.85rem', color:'var(--text-muted)'}}>Shared File Path:</label>
                    <div style={{fontFamily:'monospace', background:'#f1f5f9', padding:'8px 12px', borderRadius:4, marginTop:4}}>
                      {settings.excel_log_path}
                    </div>
                  </div>
                  <div>
                    <label style={{fontSize:'0.85rem', color:'var(--text-muted)'}}>Last Successful Sync:</label>
                    <div style={{fontWeight:600, marginTop:8}}>{settings.last_excel_sync}</div>
                  </div>
                </div>

                <div style={{display:'flex', alignItems:'center', gap:16}}>
                  <button className="btn btn-primary" onClick={handleRebuildExcel}>
                    <RefreshCw size={16} /> Rebuild Shared Excel Log from SQLite
                  </button>
                  <span style={{fontSize:'0.85rem', color:'var(--text-muted)'}}>
                    Total Rows logged: <strong>{settings.excel_row_count}</strong>
                  </span>
                </div>
              </div>

              <div className="card">
                <div className="card-title"><Sparkles size={20} /> Machine Learning & Assistant Model Configuration</div>
                <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:16}}>
                  <div>
                    <p><strong>Candidate Ranker:</strong> Random Forest Classifier</p>
                    <p style={{marginTop:6}}><strong>Engine Version:</strong> <code>{settings.model_version}</code></p>
                    <p style={{marginTop:6}}><strong>Model Status:</strong> {settings.model_status}</p>
                  </div>
                  <div>
                    <p><strong>Conversational AI Engine:</strong> Ollama Local LLM</p>
                    <p style={{marginTop:6}}><strong>LLM Model:</strong> <code>{ollamaStatus.model || 'gemma3:4b'}</code></p>
                    <p style={{marginTop:6}}>
                      <strong>Ollama Status: </strong>
                      <span className={`badge ${ollamaStatus.online ? 'badge-success' : 'badge-danger'}`}>
                        {ollamaStatus.online ? 'Online & Ready' : 'Offline'}
                      </span>
                    </p>
                  </div>
                </div>
                <p style={{marginTop:8, color:'var(--text-muted)'}}>
                  Ollama runs locally at <code>{ollamaStatus.base_url || 'http://localhost:11434'}</code> with model <code>{ollamaStatus.model || 'gemma3:4b'}</code> for privacy and offline reasoning.
                </p>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* DEDICATED EMPLOYEE PROFILE MODAL */}
      {selectedProfile && (
        <div className="modal-overlay">
          <div className="modal-card" style={{maxWidth:750}}>
            <div className="modal-header">
              <div style={{display:'flex', alignItems:'center', gap:12}}>
                <div style={{width:48, height:48, borderRadius:'50%', background:'var(--primary)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, fontWeight:700}}>
                  {selectedProfile.employee.name.charAt(0)}
                </div>
                <div>
                  <h3 style={{fontSize:'1.3rem'}}>{selectedProfile.employee.name}</h3>
                  <p style={{fontSize:'0.85rem', color:'var(--text-muted)'}}>
                    <Mail size={12} style={{marginRight:4}} /> {selectedProfile.employee.email} | <MapPin size={12} style={{marginRight:4}} /> {selectedProfile.employee.location}
                  </p>
                </div>
              </div>
              <button className="close-btn" onClick={() => setSelectedProfile(null)}>X</button>
            </div>

            {/* Profile Content */}
            <div style={{display:'flex', flexDirection:'column', gap:16}}>
              {/* Workload Progress Card */}
              <div className="card" style={{padding:16, margin:0, background:'#f8fafc'}}>
                <div style={{display:'flex', justifyContent:'space-between', marginBottom:8}}>
                  <strong>Current Workload Capacity</strong>
                  <span>{selectedProfile.employee.current_workload}h / {selectedProfile.employee.working_hours_per_week}h assigned</span>
                </div>
                <div style={{width:'100%', height:10, background:'#e2e8f0', borderRadius:5, overflow:'hidden'}}>
                  <div style={{
                    width: `${Math.min(100, (selectedProfile.employee.current_workload / selectedProfile.employee.working_hours_per_week) * 100)}%`,
                    height: '100%',
                    background: selectedProfile.employee.remaining_capacity < 5 ? 'var(--danger)' : 'var(--primary)'
                  }} />
                </div>
                <div style={{display:'flex', justifyContent:'space-between', fontSize:'0.85rem', marginTop:6, color:'var(--text-muted)'}}>
                  <span>Remaining Headroom: <strong>{selectedProfile.employee.remaining_capacity}h</strong></span>
                  <span>Tasks Completed: <strong>{selectedProfile.completed_assignments_count}</strong> ({selectedProfile.total_hours_delivered}h delivered)</span>
                </div>
              </div>

              {/* Skills Chip List */}
              <div>
                <h4 style={{fontSize:'0.95rem', marginBottom:8}}><Star size={14} style={{marginRight:4, color:'var(--warning)'}} /> Skill Proficiencies</h4>
                <div style={{display:'flex', flexWrap:'wrap', gap:8}}>
                  {selectedProfile.employee.skills.split(',').map((sk, idx) => (
                    <span key={idx} className="badge badge-info" style={{fontSize:'0.85rem', padding:'6px 12px'}}>
                      {sk}
                    </span>
                  ))}
                </div>
              </div>

              {/* Active & Historical Tasks */}
              <div>
                <h4 style={{fontSize:'0.95rem', marginBottom:8}}><Briefcase size={14} style={{marginRight:4}} /> Assigned Tasks History</h4>
                {selectedProfile.assignment_history.length === 0 ? (
                  <p style={{fontSize:'0.85rem', color:'var(--text-muted)'}}>No assignment history recorded yet.</p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Task</th>
                        <th>Effort</th>
                        <th>Status</th>
                        <th>Assigned Date</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedProfile.assignment_history.map(a => (
                        <tr key={a.id}>
                          <td><strong>{a.task_title}</strong></td>
                          <td>{a.estimated_hours}h</td>
                          <td>
                            <span className={`badge ${a.status === 'completed' ? 'badge-success' : a.status === 'active' ? 'badge-info' : 'badge-warning'}`}>
                              {a.status}
                            </span>
                          </td>
                          <td><small>{new Date(a.assigned_at).toLocaleDateString()}</small></td>
                          <td>
                            {a.status === 'active' && (
                              <button className="btn btn-success btn-sm" onClick={() => handleCompleteTask(a.task_id)}>
                                Complete
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div style={{display:'flex', justifyContent:'flex-end', marginTop:20}}>
              <button className="btn btn-secondary" onClick={() => setSelectedProfile(null)}>Close Profile</button>
            </div>
          </div>
        </div>
      )}

      {/* Add Employee Modal */}
      {showAddEmp && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Add New Employee</h3>
              <button className="close-btn" onClick={() => setShowAddEmp(false)}>X</button>
            </div>
            <form onSubmit={handleCreateEmployee}>
              <div className="form-group">
                <label>Full Name</label>
                <input type="text" required value={newEmp.name} onChange={e => setNewEmp({...newEmp, name: e.target.value})} placeholder="e.g. Alice Smith" />
              </div>
              <div className="form-group">
                <label>Email Address</label>
                <input type="email" required value={newEmp.email} onChange={e => setNewEmp({...newEmp, email: e.target.value})} placeholder="e.g. alice@example.com" />
              </div>
              <div className="form-group">
                <label>Skills & Proficiencies (Format: Skill:Level,Skill:Level)</label>
                <input type="text" required value={newEmp.skills} onChange={e => setNewEmp({...newEmp, skills: e.target.value})} placeholder="Python:4,FastAPI:3,SQL:4" />
              </div>
              <div className="form-group">
                <label>Location</label>
                <input type="text" value={newEmp.location} onChange={e => setNewEmp({...newEmp, location: e.target.value})} placeholder="New York or Remote" />
              </div>
              <div className="form-group">
                <label>Weekly Working Hours Capacity</label>
                <input type="number" required value={newEmp.working_hours_per_week} onChange={e => setNewEmp({...newEmp, working_hours_per_week: parseFloat(e.target.value)})} />
              </div>
              <div style={{display:'flex', justifyContent:'flex-end', gap:10, marginTop:20}}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddEmp(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={loading}>Save Employee</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Task Modal */}
      {showAddTask && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Create New Task</h3>
              <button className="close-btn" onClick={() => setShowAddTask(false)}>X</button>
            </div>
            <form onSubmit={handleCreateTask}>
              <div className="form-group">
                <label>Task Title</label>
                <input type="text" required value={newTask.title} onChange={e => setNewTask({...newTask, title: e.target.value})} placeholder="e.g. Build Auth API" />
              </div>
              <div className="form-group">
                <label>Required Skills (Format: Skill:Level)</label>
                <input type="text" required value={newTask.required_skills} onChange={e => setNewTask({...newTask, required_skills: e.target.value})} placeholder="Python:3,FastAPI:2" />
              </div>
              <div className="form-group">
                <label>Location Requirement</label>
                <input type="text" value={newTask.location} onChange={e => setNewTask({...newTask, location: e.target.value})} placeholder="Remote or New York" />
              </div>
              <div className="form-group">
                <label>Estimated Effort Hours</label>
                <input type="number" required value={newTask.estimated_hours} onChange={e => setNewTask({...newTask, estimated_hours: parseFloat(e.target.value)})} />
              </div>
              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
                <div className="form-group">
                  <label>Priority</label>
                  <select value={newTask.priority} onChange={e => setNewTask({...newTask, priority: e.target.value})}>
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                    <option value="Critical">Critical</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Urgency</label>
                  <select value={newTask.urgency} onChange={e => setNewTask({...newTask, urgency: e.target.value})}>
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                    <option value="Urgent">Urgent</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label>Deadline</label>
                <input type="datetime-local" required value={newTask.deadline} onChange={e => setNewTask({...newTask, deadline: e.target.value})} />
              </div>
              <div style={{display:'flex', justifyContent:'flex-end', gap:10, marginTop:20}}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddTask(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={loading}>Create Task</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
