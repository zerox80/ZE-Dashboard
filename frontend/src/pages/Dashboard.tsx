import React, { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FiPlus, FiDownload, FiCalendar, FiClock, FiDollarSign, FiTrash2 } from 'react-icons/fi'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import api from '../api'
import UploadModal from '../components/UploadModal'
import CommandPalette from '../components/CommandPalette'
import AuditModal from '../components/AuditModal'

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
    version?: number
    file_extension: string
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const Dashboard: React.FC = () => {
    const [isUploadOpen, setIsUploadOpen] = useState(false)
    const [isAuditOpen, setIsAuditOpen] = useState(false)
    const [auditContract, setAuditContract] = useState<{ id: number, title: string } | null>(null)
    const [editingContract, setEditingContract] = useState<Contract | null>(null)
    const queryClient = useQueryClient()

    const { data: contracts, isLoading, refetch } = useQuery<Contract[]>(['contracts'], async () => {
        const res = await api.get('/contracts')
        return res.data
    })

    const handleDelete = async (id: number, title: string) => {
        if (window.confirm(`Möchten Sie den Vertrag "${title}" wirklich löschen?`)) {
            try {
                await api.delete(`/contracts/${id}`)
                queryClient.invalidateQueries(['contracts'])
            } catch (e) {
                console.error("Delete failed", e)
                alert("Fehler beim Löschen des Vertrags")
            }
        }
    }

    // Analytics
    const activeContracts = contracts?.length || 0;
    const totalValue = contracts?.reduce((acc, c) => acc + (c.value || 0), 0) || 0;

    // Group by month for spending chart
    const spendingData = React.useMemo(() => {
        if (!contracts) return [];

        const months: { [key: string]: number } = {};
        const allMonths = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];

        allMonths.forEach(m => months[m] = 0);

        contracts.forEach(contract => {
            if (!contract.start_date || !contract.value) return;
            const date = new Date(contract.start_date);
            const monthIndex = date.getMonth();
            const monthName = allMonths[monthIndex];
            if (months[monthName] !== undefined) {
                months[monthName] += contract.value;
            }
        });

        return allMonths.map(name => ({
            name,
            amount: months[name]
        }));
    }, [contracts]);

    // Cost Distribution (Donut Chart)
    const costDistributionData = React.useMemo(() => {
        if (!contracts) return [];
        const sorted = [...contracts].sort((a, b) => (b.value || 0) - (a.value || 0));

        const topItems = sorted.slice(0, 4);
        const others = sorted.slice(4);

        const data = topItems.map(c => ({ name: c.title, value: c.value || 0 }));

        if (others.length > 0) {
            const othersValue = others.reduce((acc, c) => acc + (c.value || 0), 0);
            data.push({ name: 'Andere', value: othersValue });
        }

        return data.filter(d => d.value > 0);
    }, [contracts]);

    const handleDownload = async (id: number, title: string, extension: string) => {
        try {
            const response = await api.get(`/contracts/${id}/download`, {
                responseType: 'blob'
            });
            // Normalize extension (ensure it has a dot)
            let ext = extension || '.pdf';
            if (!ext.startsWith('.')) {
                ext = '.' + ext;
            }

            const isPdf = ext.toLowerCase() === '.pdf';
            const blobType = isPdf ? 'application/pdf' : undefined;
            const url = window.URL.createObjectURL(new Blob([response.data], { type: blobType }));
            const link = document.createElement('a');
            link.href = url;

            const filename = title.endsWith(ext) ? title : `${title}${ext}`;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (e: any) {
            console.error("Download failed", e)
            if (e.response && e.response.status === 404) {
                alert("Datei wurde auf dem Server nicht gefunden. Bitte laden Sie die Datei erneut hoch.");
            } else {
                alert("Fehler beim Herunterladen der Datei.");
            }
        }
    }

    if (isLoading) return <div className="p-8 text-center text-gray-400">Lade Dashboard...</div>

    return (
        <div className="w-full bg-gray-950 p-0 md:p-8">
            <CommandPalette />

            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 p-4 md:p-0">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">Vertragsübersicht</h1>
                    <p className="text-gray-400">Verwalten und verfolgen Sie Ihre Unternehmensvereinbarungen.</p>
                </div>
                <button
                    onClick={() => setIsUploadOpen(true)}
                    className="mt-4 md:mt-0 w-full md:w-auto flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-lg shadow-blue-500/20"
                >
                    <FiPlus />
                    <span>Neuer Vertrag</span>
                </button>
            </div>

            {/* Analytics Row */}
            {/* Analytics Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 backdrop-blur-sm">
                    <h3 className="text-gray-400 text-sm font-medium mb-2">Gesamtwert</h3>
                    <p className="text-2xl lg:text-3xl font-bold text-green-400 break-all sm:break-normal">{totalValue.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}</p>
                </div>
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 backdrop-blur-sm">
                    <h3 className="text-gray-400 text-sm font-medium mb-2">Aktive Verträge</h3>
                    <p className="text-3xl font-bold text-white">{activeContracts}</p>
                </div>

                <div className="md:col-span-2 bg-gray-800/50 border border-gray-700 rounded-xl p-4 backdrop-blur-sm flex flex-col md:flex-row gap-4 min-w-0">
                    {/* Bar Chart Section */}
                    <div className="flex-1 min-w-0">
                        <p className="text-xs text-gray-400 mb-2">Ausgabentrend</p>
                        <div className="h-48 md:h-64 w-full relative">
                            <div className="absolute inset-0">
                                <ResponsiveContainer width="99%" height="100%">
                                    <BarChart data={spendingData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                        <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                                        <YAxis
                                            stroke="#9ca3af"
                                            fontSize={12}
                                            tickLine={false}
                                            axisLine={false}
                                            width={80}
                                            tickFormatter={(value) => {
                                                if (value >= 1000000) return `${(value / 1000000).toLocaleString('de-DE', { maximumFractionDigits: 1 })} Mio. €`;
                                                if (value >= 1000) return `${(value / 1000).toLocaleString('de-DE', { maximumFractionDigits: 0 })} Tsd. €`;
                                                return `${value.toLocaleString('de-DE')} €`;
                                            }}
                                        />
                                        <RechartsTooltip
                                            cursor={{ fill: '#374151', opacity: 0.5 }}
                                            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '0.5rem', color: '#fff' }}
                                            itemStyle={{ color: '#fff' }}
                                            labelStyle={{ color: '#fff' }}
                                            formatter={(value: number) => [value.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' }), 'Betrag']}
                                        />
                                        <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                    {/* Donut Chart Section */}
                    <div className="flex-1 min-w-0 border-t md:border-t-0 md:border-l border-gray-700 pt-4 md:pt-0 md:pl-4">
                        <p className="text-xs text-gray-400 mb-2">Kostenverteilung</p>
                        <div className="h-48 md:h-64 w-full relative">
                            <div className="absolute inset-0">
                                <ResponsiveContainer width="99%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={costDistributionData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={40}
                                            outerRadius={60}
                                            paddingAngle={5}
                                            dataKey="value"
                                        >
                                            {costDistributionData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <RechartsTooltip
                                            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '0.5rem', color: '#fff' }}
                                            itemStyle={{ color: '#fff' }}
                                            labelStyle={{ display: 'none' }}
                                            formatter={(value: number, name: string) => {
                                                const percent = totalValue > 0 ? (value / totalValue * 100) : 0;
                                                return [`${percent.toLocaleString('de-DE', { maximumFractionDigits: 1 })}%`, name];
                                            }}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
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
                            <div className="flex gap-2">
                                <span className={`text-xs font-medium px-2 py-1 rounded ${new Date(contract.end_date) < new Date() ? 'bg-red-900/50 text-red-300' : 'bg-emerald-900/50 text-emerald-300'}`}>
                                    {new Date(contract.end_date) < new Date() ? 'Abgelaufen' : 'Aktiv'}
                                </span>
                                <button
                                    onClick={() => {
                                        setAuditContract({ id: contract.id, title: contract.title });
                                        setIsAuditOpen(true);
                                    }}
                                    className="p-1 px-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs transition-colors"
                                >
                                    Ansicht
                                </button>
                                <button
                                    onClick={() => {
                                        setEditingContract(contract);
                                        setIsUploadOpen(true);
                                    }}
                                    className="p-1 px-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs transition-colors"
                                >
                                    Bearbeiten
                                </button>
                                <button
                                    onClick={() => handleDelete(contract.id, contract.title)}
                                    className="p-1 px-2 bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded text-xs transition-colors"
                                    title="Löschen"
                                >
                                    <FiTrash2 />
                                </button>
                            </div>
                        </div>

                        <h3 className="text-lg font-semibold text-white mb-1">{contract.title}</h3>

                        {/* Tags */}
                        <div className="flex flex-wrap gap-2 mb-3">
                            {contract.tags?.map((tag, i) => (
                                <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 border border-gray-600">#{tag.name}</span>
                            ))}
                        </div>

                        <p className="text-sm text-gray-400 mb-4 line-clamp-2 h-10">{contract.description || "Keine Beschreibung vorhanden."}</p>

                        <div className="flex justify-between items-center text-xs text-gray-500 mb-6 border-t border-gray-700/50 pt-4">
                            <div className="flex items-center gap-1">
                                <FiClock />
                                <span>{new Date(contract.start_date).toLocaleDateString('de-DE')}</span>
                            </div>
                            <div className="flex items-center gap-1 font-bold text-gray-400">
                                <span>€</span>
                                <span>{contract.value?.toLocaleString('de-DE') || 0}</span>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            <button
                                onClick={() => handleDownload(contract.id, contract.title, contract.file_extension)}
                                className="flex-1 flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-gray-200 py-2 rounded-lg transition-colors text-sm"
                            >
                                <FiDownload />
                                <span>PDF</span>
                            </button>
                            <button className="px-3 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-400 hover:text-white transition-colors">
                                v{contract.version || 1}
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            <UploadModal
                isOpen={isUploadOpen}
                onClose={() => {
                    setIsUploadOpen(false);
                    setEditingContract(null);
                }}
                initialData={editingContract}
            />
            <AuditModal
                isOpen={isAuditOpen}
                onClose={() => setIsAuditOpen(false)}
                contractId={auditContract?.id || null}
                contractTitle={auditContract?.title || ''}
            />
        </div>
    )
}

export default Dashboard
