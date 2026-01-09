import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiX, FiActivity, FiUser } from 'react-icons/fi';
import api from '../api';

interface AuditLog {
    id: number;
    user_id?: number;
    username?: string;
    action: string;
    details: string;
    timestamp: string;
    ip_address?: string;
}

interface AuditModalProps {
    isOpen: boolean;
    onClose: () => void;
    contractId: number | null;
    contractTitle: string;
}

export default function AuditModal({ isOpen, onClose, contractId, contractTitle }: AuditModalProps) {
    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (isOpen && contractId) {
            fetchLogs();
        }
    }, [isOpen, contractId]);

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const res = await api.get(`/contracts/${contractId}/audit`);
            setLogs(res.data);
        } catch (error) {
            console.error("Failed to fetch audit logs", error);
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                onClick={onClose}
            >
                <motion.div
                    initial={{ scale: 0.95, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.95, opacity: 0 }}
                    className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-4xl max-h-[80vh] flex flex-col shadow-2xl"
                    onClick={e => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900 rounded-t-xl">
                        <div>
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <FiActivity className="text-blue-400" />
                                Audit-Log: {contractTitle}
                            </h2>
                            <p className="text-gray-400 text-sm mt-1">
                                Vollständige Historie aller Aktivitäten für diesen Vertrag.
                            </p>
                        </div>
                        <button onClick={onClose} className="p-2 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors">
                            <FiX size={24} />
                        </button>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-6">
                        {loading ? (
                            <div className="flex justify-center items-center h-full">
                                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                            </div>
                        ) : logs.length === 0 ? (
                            <div className="text-center text-gray-500 py-12">
                                Keine Aktivitäten protokolliert.
                            </div>
                        ) : (
                            <div className="relative overflow-x-auto rounded-lg border border-gray-800">
                                <table className="w-full text-left text-sm text-gray-400">
                                    <thead className="bg-gray-800 text-gray-300 uppercase font-medium">
                                        <tr>
                                            <th className="px-6 py-3">Zeitpunkt</th>
                                            <th className="px-6 py-3">Benutzer</th>
                                            <th className="px-6 py-3">Aktion</th>
                                            <th className="px-6 py-3">Details</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-800">
                                        {logs.map((log) => (
                                            <tr key={log.id} className="hover:bg-gray-800/50 transition-colors">
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    {new Date(log.timestamp).toLocaleString('de-DE')}
                                                </td>
                                                <td className="px-6 py-4 flex items-center gap-2 text-white">
                                                    <div className="p-1 bg-gray-700 rounded-full">
                                                        <FiUser size={12} />
                                                    </div>
                                                    {log.username || `User ${log.user_id}`}
                                                </td>
                                                <td className="px-6 py-4">
                                                    <span className={`px-2 py-1 rounded text-xs font-bold ${log.action === 'UPLOAD' ? 'bg-green-900/50 text-green-400' :
                                                        log.action === 'DOWNLOAD' ? 'bg-blue-900/50 text-blue-400' :
                                                            log.action === 'UPDATE_CONTRACT' ? 'bg-yellow-900/50 text-yellow-400' :
                                                                'bg-gray-700 text-gray-300'
                                                        }`}>
                                                        {log.action}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 text-xs font-mono whitespace-pre-wrap break-words max-w-lg">
                                                    {log.details.replace(/\[CID:\d+\]\s*/, '')}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}
