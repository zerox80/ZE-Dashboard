import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FiPlus, FiDownload, FiCalendar, FiClock, FiDollarSign } from 'react-icons/fi'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import api from '../api'
import UploadModal from '../components/UploadModal'
import CommandPalette from '../components/CommandPalette'

interface Contract {
    id: number
    title: string
    description: string
    start_date: string
    end_date: string
    file_path: string
    uploaded_at: string
    value: number
    tags: { name: string, color: string }[]
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

const Dashboard: React.FC = () => {
    const [isUploadOpen, setIsUploadOpen] = useState(false)
    const { data: contracts, isLoading } = useQuery<Contract[]>(['contracts'], async () => {
        const res = await api.get('/contracts')
        return res.data
    })

    // Analytics
    const activeContracts = contracts?.length || 0;
    const totalValue = contracts?.reduce((acc, c) => acc + (c.value || 0), 0) || 0;

    const statusData = [
        { name: 'Active', value: activeContracts },
        { name: 'Review', value: Math.floor(Math.random() * 2) },
        { name: 'Expiring', value: Math.floor(Math.random() * 2) },
    ];

    // Group by month for spending chart (Simulated)
    const spendingData = [
        { name: 'Jan', amount: 4000 },
        { name: 'Feb', amount: 3000 },
        { name: 'Mar', amount: 2000 },
        { name: 'Apr', amount: 2780 },
        { name: 'May', amount: 1890 },
        { name: 'Jun', amount: 2390 },
        { name: 'Jul', amount: 3490 },
    ];

    const handleDownload = async (id: number, title: string) => {
        try {
            const response = await api.get(`/contracts/${id}/download`, {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `${title}.file`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (e) {
            console.error("Download failed", e)
        }
    }

    if (isLoading) return <div className="p-8 text-center text-gray-400">Loading dashboard...</div>

    return (
        <div>
            <CommandPalette />

            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">Contract Overview</h1>
                    <p className="text-gray-400">Manage and track your company agreements.</p>
                </div>
                <button
                    onClick={() => setIsUploadOpen(true)}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-lg shadow-blue-500/20"
                >
                    <FiPlus />
                    <span>New Contract</span>
                </button>
            </div>

            {/* Analytics Row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 backdrop-blur-sm">
                    <h3 className="text-gray-400 text-sm font-medium mb-2">Total Value</h3>
                    <p className="text-3xl font-bold text-green-400">${totalValue.toLocaleString()}</p>
                </div>
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 backdrop-blur-sm">
                    <h3 className="text-gray-400 text-sm font-medium mb-2">Active Contracts</h3>
                    <p className="text-3xl font-bold text-white">{activeContracts}</p>
                </div>

                <div className="md:col-span-2 bg-gray-800/50 border border-gray-700 rounded-xl p-4 backdrop-blur-sm flex items-center">
                    <div className="flex-1 h-24">
                        <p className="text-xs text-gray-400 mb-2">Spending Trend</p>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={spendingData}>
                                <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                <RechartsTooltip cursor={{ fill: 'transparent' }} contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Contract List */}
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                {contracts?.map((contract) => (
                    <div key={contract.id} className="bg-gray-800 border border-gray-700 rounded-xl p-6 hover:border-gray-600 transition-all group relative hover:-translate-y-1 hover:shadow-xl">
                        <div className="flex justify-between items-start mb-4">
                            <div className="p-3 bg-blue-500/10 rounded-lg text-blue-400 group-hover:bg-blue-500/20 transition-colors">
                                <FiCalendar size={24} />
                            </div>
                            <span className={`text-xs font-medium px-2 py-1 rounded ${new Date(contract.end_date) < new Date() ? 'bg-red-900/50 text-red-300' : 'bg-emerald-900/50 text-emerald-300'}`}>
                                {new Date(contract.end_date) < new Date() ? 'Expired' : 'Active'}
                            </span>
                        </div>

                        <h3 className="text-lg font-semibold text-white mb-1">{contract.title}</h3>

                        {/* Tags */}
                        <div className="flex flex-wrap gap-2 mb-3">
                            {contract.tags?.map((tag, i) => (
                                <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 border border-gray-600">#{tag.name}</span>
                            ))}
                        </div>

                        <p className="text-sm text-gray-400 mb-4 line-clamp-2 h-10">{contract.description || "No description provided."}</p>

                        <div className="flex justify-between items-center text-xs text-gray-500 mb-6 border-t border-gray-700/50 pt-4">
                            <div className="flex items-center gap-1">
                                <FiClock />
                                <span>{new Date(contract.start_date).toLocaleDateString()}</span>
                            </div>
                            <div className="flex items-center gap-1 font-bold text-gray-400">
                                <FiDollarSign />
                                <span>{contract.value?.toLocaleString() || 0}</span>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            <button
                                onClick={() => handleDownload(contract.id, contract.title)}
                                className="flex-1 flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-gray-200 py-2 rounded-lg transition-colors text-sm"
                            >
                                <FiDownload />
                                <span>PDF</span>
                            </button>
                            {/* Version history button placeholder */}
                            <button className="px-3 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-400 hover:text-white transition-colors">
                                v{contract.version || 1}
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            <UploadModal isOpen={isUploadOpen} onClose={() => setIsUploadOpen(false)} />
        </div>
    )
}

export default Dashboard
