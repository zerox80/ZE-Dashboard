import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { FiUploadCloud, FiX } from 'react-icons/fi'
import api from '../api'
import { useQueryClient } from '@tanstack/react-query'

interface UploadModalProps {
    isOpen: boolean
    onClose: () => void
}

const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose }) => {
    const [file, setFile] = useState<File | null>(null)
    const [title, setTitle] = useState('')
    const [description, setDescription] = useState('')
    const [value, setValue] = useState('')
    const [tags, setTags] = useState('')
    const [startDate, setStartDate] = useState('')
    const [endDate, setEndDate] = useState('')
    const [uploading, setUploading] = useState(false)

    const queryClient = useQueryClient()

    const onDrop = useCallback((acceptedFiles: File[]) => {
        if (acceptedFiles.length > 0) {
            setFile(acceptedFiles[0])
        }
    }, [])

    const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, maxFiles: 1 })

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!file || !title || !startDate || !endDate) return

        setUploading(true)
        const formData = new FormData()
        formData.append('file', file)
        formData.append('title', title)
        formData.append('description', description)
        formData.append('value', value || '0')
        formData.append('tags', tags)
        formData.append('start_date', new Date(startDate).toISOString())
        formData.append('end_date', new Date(endDate).toISOString())

        try {
            await api.post('/contracts', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })
            queryClient.invalidateQueries(['contracts'])
            onClose()
            // Reset form
            setFile(null)
            setTitle('')
            setDescription('')
            setValue('')
            setTags('')
            setStartDate('')
            setEndDate('')
        } catch (error) {
            console.error('Upload failed', error)
        } finally {
            setUploading(false)
        }
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
                        <div className="bg-gray-900 border border-gray-700 w-full max-w-xl rounded-2xl shadow-2xl pointer-events-auto flex flex-col max-h-[90vh] overflow-y-auto">
                            <div className="flex justify-between items-center p-6 border-b border-gray-800">
                                <h3 className="text-xl font-semibold text-white">Upload Contract</h3>
                                <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                                    <FiX size={24} />
                                </button>
                            </div>

                            <form onSubmit={handleSubmit} className="p-6 space-y-4">
                                <div {...getRootProps()} className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${isDragActive ? 'border-blue-500 bg-blue-500/10' : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'}`}>
                                    <input {...getInputProps()} />
                                    <FiUploadCloud className="mx-auto text-4xl text-gray-400 mb-3" />
                                    {file ? (
                                        <p className="text-blue-400 font-medium">{file.name}</p>
                                    ) : (
                                        <p className="text-gray-400">Drag & drop a file here, or click to select</p>
                                    )}
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-400 mb-1">Title</label>
                                        <input type="text" value={title} onChange={e => setTitle(e.target.value)} className="w-full bg-gray-800 border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" required />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-400 mb-1">Value ($)</label>
                                        <input type="number" value={value} onChange={e => setValue(e.target.value)} className="w-full bg-gray-800 border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" />
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-1">Description</label>
                                    <textarea value={description} onChange={e => setDescription(e.target.value)} className="w-full bg-gray-800 border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" rows={2} />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-1">Tags (comma separated)</label>
                                    <input type="text" value={tags} onChange={e => setTags(e.target.value)} placeholder="Software, SaaS, 2024" className="w-full bg-gray-800 border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" />
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-400 mb-1">Start Date</label>
                                        <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="w-full bg-gray-800 border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" required />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-400 mb-1">End Date</label>
                                        <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="w-full bg-gray-800 border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" required />
                                    </div>
                                </div>

                                <div className="pt-4">
                                    <button type="submit" disabled={uploading} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 rounded-lg transition-colors disabled:opacity-50">
                                        {uploading ? 'Uploading...' : 'Upload Contract'}
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

export default UploadModal
