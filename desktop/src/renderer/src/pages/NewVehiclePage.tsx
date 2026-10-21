import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { endpoints } from '../api/endpoints'
import { emptyVehicle, VehicleForm } from '../components/VehicleForm'
import { PageHeader } from '../components/ui'
import { useToast } from '../context/ToastContext'

export function NewVehiclePage(): React.JSX.Element {
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  return (
    <div>
      <PageHeader title="Registrar vehículo"
        subtitle="Al guardarlo aparecerá de inmediato en la página web. Después podrás agregar fotografías." />
      {error && <div className="alert alert-critical">{error}</div>}
      <section className="card">
        <VehicleForm initial={emptyVehicle()} submitLabel="Registrar vehículo" serverErrors={serverErrors}
          onSubmit={async (data) => {
            setError(null)
            try {
              const v = await endpoints.createVehicle(data)
              queryClient.invalidateQueries({ queryKey: ['vehicles'] })
              toast('success', 'Vehículo registrado', `${v.stock_number} · ${v.brand} ${v.model}`)
              navigate(`/vehiculos/${v.id}`)
            } catch (e) {
              if (e instanceof ApiError) {
                setServerErrors(e.fields)
                setError(e.message)
              } else throw e
            }
          }} />
      </section>
    </div>
  )
}
