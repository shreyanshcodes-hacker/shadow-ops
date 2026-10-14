'use client';

import { forwardRef, useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { Label } from '@/components/ui/Label';
import { Checkbox } from '@/components/ui/Checkbox';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@/components/ui/Popover';
import { ChevronDown, Search, Check } from 'lucide-react';
import { api } from '@/lib/api';

interface Asset {
  id: string;
  name: string;
  type: string;
  criticality: string;
  status: string;
}

interface AssetMultiSelectProps {
  workspaceId: string;
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  label?: string;
  className?: string;
}

export const AssetMultiSelect = forwardRef<HTMLButtonElement, AssetMultiSelectProps>(
  ({ workspaceId, selected, onChange, placeholder = 'Select assets...', label, className, ...props }, ref) => {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState('');
    const [assets, setAssets] = useState<Asset[]>([]);
    const [loading, setLoading] = useState(false);
    const popoverRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      const fetchAssets = async () => {
        setLoading(true);
        try {
          const data = await api.listAssets(workspaceId);
          setAssets(data);
        } catch {
          setAssets([]);
        } finally {
          setLoading(false);
        }
      };
      fetchAssets();
    }, [workspaceId]);

    const filteredAssets = assets.filter(asset =>
      asset.name.toLowerCase().includes(search.toLowerCase()) ||
      asset.type.toLowerCase().includes(search.toLowerCase())
    );

    const toggleAsset = (assetId: string) => {
      onChange(selected.includes(assetId)
        ? selected.filter(id => id !== assetId)
        : [...selected, assetId]
      );
    };

    const selectedCount = selected.length;

    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            ref={ref}
            variant="outline"
            className={cn('w-full justify-between text-left h-auto py-3', className)}
            {...props}
          >
            <div className="flex flex-col gap-1">
              {label && <Label className="text-xs font-medium text-gray-500">{label}</Label>}
              <div className="flex items-center justify-between">
                <span className={selectedCount > 0 ? 'text-gray-900' : 'text-gray-500'}>
                  {selectedCount > 0
                    ? `${selectedCount} asset${selectedCount > 1 ? 's' : ''} selected`
                    : placeholder}
                </span>
                <ChevronDown className="h-4 w-4 text-gray-400" />
              </div>
            </div>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-96 p-0" align="start">
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-2">
              <Label className="font-medium">Select Assets</Label>
              <span className="text-sm text-gray-500">{assets.length} available</span>
            </div>
            <Input
              placeholder="Search assets..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full"
            />
            <div className="max-h-64 overflow-y-auto space-y-1">
              {loading ? (
                <div className="py-4 text-center text-gray-500">Loading assets...</div>
              ) : filteredAssets.length === 0 ? (
                <div className="py-4 text-center text-gray-500">No assets found</div>
              ) : (
                filteredAssets.map(asset => (
                  <label
                    key={asset.id}
                    className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg cursor-pointer transition-colors"
                  >
                    <Checkbox
                      checked={selected.includes(asset.id)}
                      onCheckedChange={() => toggleAsset(asset.id)}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">{asset.name}</p>
                      <p className="text-xs text-gray-500 flex items-center gap-2">
                        <span className="capitalize">{asset.type}</span>
                        <span className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-600">{asset.criticality}</span>
                        <span className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-600">{asset.status}</span>
                      </p>
                    </div>
                    {selected.includes(asset.id) && <Check className="h-4 w-4 text-accent-DEFAULT" />}
                  </label>
                ))
              )}
            </div>
            {selectedCount > 0 && (
              <Button variant="outline" size="sm" className="w-full" onClick={() => onChange([])}>
                Clear all ({selectedCount})
              </Button>
            )}
          </div>
        </PopoverContent>
      </Popover>
    );
  }
);

AssetMultiSelect.displayName = 'AssetMultiSelect';