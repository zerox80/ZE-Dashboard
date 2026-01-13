import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiX, FiFolder } from 'react-icons/fi'

interface ListModalProps {
    isOpen: boolean
    onClose: () => void
    onSubmit: (data: { name: string; description: string; color: string }) => void
    initialData?: { id?: number; name: string; description?: string; color: string } | null
    isLoading?: boolean
}

const PRESET_COLORS = [
    '#6366f1', // Indigo
    '#3b82f6', // Blue
    '#10b981', // Emerald
    '#f59e0b', // Amber
    '#ef4444', // Red
    '#ec4899', // Pink
    '#8b5cf6', // Violet
    '#06b6d4', // Cyan
]

const ListModal: React.FC<ListModalProps> = ({ isOpen, onClose, onSubmit, initialData, isLoading }) => {
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [color, setColor] = useState('#6366f1')

    useEffect(() => {
        if (isOpen && initialData) {
            setName(initialData.name || '')
            setDescription(initialData.description || '')
            setColor(initialData.color || '#6366f1')
        } else if (isOpen && !initialData) {
            setName('')
            setDescription('')
            setColor('#6366f1')
        }
    }, [isOpen, initialData])

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (!name.trim()) return
        onSubmit({ name: name.trim(), description: description.trim(), color })
    }

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40"
                        onClick={onClose}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
                    >
                        <div className="bg-gray-900 border border-gray-700 w-full max-w-md rounded-2xl shadow-2xl pointer-events-auto">
                            <div className="flex justify-between items-center p-6 border-b border-gray-800">
                                <div className="flex items-center gap-3">
                                    <div
                                        className="p-2 rounded-lg"
                                        style={{ backgroundColor: `${color}20` }}
                                    >
                                        <FiFolder size={20} style={{ color }} />
                                    </div>
                                    <h3 className="text-xl font-semibold text-white">
                                        {initialData ? 'Liste bearbeiten' : 'Neue Liste erstellen'}
                                    </h3>
                                </div>
                                <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                                    <FiX size={24} />
                                </button>
                            </div>

                            <form onSubmit={handleSubmit} className="p-6 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-1">Name</label>
                                    <input
                                        type="text"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="z.B. Software Lizenzen"
                                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                                        required
                                        autoFocus
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-1">Beschreibung (optional)</label>
                                    <textarea
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                        placeholder="Kurze Beschreibung der Liste..."
                                        rows={2}
                                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 resize-none"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-2">Farbe</label>
                                    <div className="flex flex-wrap gap-2">
                                        {PRESET_COLORS.map((presetColor) => (
                                            <button
                                                key={presetColor}
                                                type="button"
                                                onClick={() => setColor(presetColor)}
                                                className={`w-8 h-8 rounded-full transition-all ${color === presetColor
                                                    ? 'ring-2 ring-white ring-offset-2 ring-offset-gray-900 scale-110'
                                                    : 'hover:scale-105'
                                                    }`}
                                                style={{ backgroundColor: presetColor }}
                                            />
                                        ))}
                                        <input
                                            type="color"
                                            value={color}
                                            onChange={(e) => setColor(e.target.value)}
                                            className="w-8 h-8 rounded-full cursor-pointer bg-transparent border-2 border-dashed border-gray-600"
                                            title="Eigene Farbe wählen"
                                        />
                                    </div>
                                </div>

                                {/* Preview */}
                                <div className="pt-2">
                                    <label className="block text-sm font-medium text-gray-400 mb-2">Vorschau</label>
                                    <div
                                        className="flex items-center gap-3 p-3 rounded-lg border"
                                        style={{ borderColor: color, backgroundColor: `${color}10` }}
                                    >
                                        <div
                                            className="p-2 rounded-lg"
                                            style={{ backgroundColor: `${color}30` }}
                                        >
                                            <FiFolder size={20} style={{ color }} />
                                        </div>
                                        <div>
                                            <p className="font-medium text-white">{name || 'Listenname'}</p>
                                            <p className="text-sm text-gray-400">{description || 'Beschreibung'}</p>
                                        </div>
                                    </div>
                                </div>

                                <div className="pt-4">
                                    <button
                                        type="submit"
                                        disabled={isLoading || !name.trim()}
                                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {isLoading
                                            ? 'Speichern...'
                                            : initialData
                                                ? 'Änderungen speichern'
                                                : 'Liste erstellen'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    )
}

export default ListModal
