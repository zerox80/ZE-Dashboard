import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Layout from './components/Layout'
import { useState } from 'react'

function AppRoutes() {
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false)
    const navigate = useNavigate()

    const handleLoginSuccess = () => {
        setIsAuthenticated(true)
        navigate('/')
    }

    return (
        <Routes>
            <Route path="/login" element={
                isAuthenticated ? <Navigate to="/" /> : <Login onLoginSuccess={handleLoginSuccess} />
            } />
            <Route path="/" element={
                isAuthenticated ? <Layout><Dashboard /></Layout> : <Navigate to="/login" />
            } />
        </Routes>
    )
}

function App() {
    return (
        <Router>
            <AppRoutes />
        </Router>
    )
}

export default App
