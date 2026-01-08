import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FiLogOut, FiFileText } from 'react-icons/fi'

interface LayoutProps {
    children: React.ReactNode
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
    const navigate = useNavigate()

    const handleLogout = () => {
        // HttpOnly cookie will be cleared on next request or expires automatically
        // Force reload to clear application state
        navigate('/login')
        window.location.reload()
    }

    return (
        <div className="flex h-screen bg-gray-900 text-white overflow-hidden">
            {/* Sidebar */}
            <div className="w-64 bg-gray-800 border-r border-gray-700 p-4 flex flex-col">
                <div className="text-2xl font-bold mb-8 text-blue-500">ZE Dashboard</div>
                <nav className="flex-1 space-y-2">
                    <Link to="/" className="flex items-center space-x-2 p-3 rounded hover:bg-gray-700 transition-colors text-gray-300 hover:text-white">
                        <FiFileText />
                        <span>Contracts</span>
                    </Link>
                </nav>
                <button onClick={handleLogout} className="flex items-center space-x-2 p-3 rounded hover:bg-red-900/50 text-red-400 hover:text-red-300 transition-colors mt-auto">
                    <FiLogOut />
                    <span>Logout</span>
                </button>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-auto p-8">
                {children}
            </div>
        </div>
    )
}

export default Layout
