import type { CloudCatalogItem, ResourceParameters } from '@/service/api/provisioning';

export const acceptResponse = (requestSequence: number, currentSequence: number): boolean =>
  requestSequence === currentSequence;
export const capacityLabel = (value: number | null | undefined): string =>
  value === null || value === undefined ? '未知' : String(value);

export function resetDependencies(
  values: ResourceParameters,
  upstream: 'account' | 'zone' | 'vpc'
): ResourceParameters {
  if (upstream === 'account')
    return { ...values, zone: '', image_id: '', instance_type: '', vpc_id: '', subnet_id: '', security_group_ids: [] };
  if (upstream === 'zone')
    return { ...values, image_id: '', instance_type: '', vpc_id: '', subnet_id: '', security_group_ids: [] };
  return { ...values, subnet_id: '', security_group_ids: [] };
}

export function resourceDescription(item: CloudCatalogItem): string {
  const attrs = item.attributes;
  return [
    attrs.cpu === null || attrs.cpu === undefined ? '' : `${attrs.cpu} 核`,
    attrs.memoryMiB === null || attrs.memoryMiB === undefined ? '' : `${attrs.memoryMiB / 1024} GiB`,
    attrs.os,
    attrs.architecture,
    attrs.zone,
    attrs.cidr,
    attrs.vpcId,
    'remaining' in attrs ? `余量 ${capacityLabel(attrs.remaining)}` : '',
    item.unavailableReason
  ]
    .filter(Boolean)
    .join(' · ');
}
