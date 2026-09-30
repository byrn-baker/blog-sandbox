import copy
import unittest

from generate_flow_enrichment import build_snapshot,enrich_record,processor


def device(name='leaf1',namespace='Global',address='10.3.1.1/32'):
    return {'name':name,'role':{'name':'Leaf'},'location':{'name':'DC-A'},
            'interfaces':[{'name':'Loopback1','ip_addresses':[{'address':address,
                'parent':{'namespace':{'name':namespace}}}]}]}


class EnrichmentTests(unittest.TestCase):
    def build(self,*devices): return build_snapshot({'data':{'devices':list(devices)}})

    def test_exact_and_unknown_preserve_original(self):
        snapshot=self.build(device())
        original={'source.address':'10.3.1.1','destination.address':'8.8.8.8','flow.io.bytes':'123'}
        enriched=enrich_record(original,snapshot)
        self.assertEqual(enriched['nautobot.source.status'],'exact')
        self.assertEqual(enriched['nautobot.destination.status'],'unknown')
        self.assertNotIn('nautobot.destination.label',enriched)
        self.assertTrue(all(enriched[k]==v for k,v in original.items()))
        self.assertNotIn('nautobot.source.status',original)

    def test_shared_address_lists_both_owners(self):
        row=self.build(device(),device('leaf2'))['addresses']['10.3.1.1']
        self.assertEqual(row['status'],'shared'); self.assertEqual(len(row['owners']),2)
        self.assertIn('leaf1',row['label']); self.assertIn('leaf2',row['label'])

    def test_namespace_collision_never_picks_owner(self):
        row=self.build(device(),device('leaf2','TenantB'))['addresses']['10.3.1.1']
        self.assertEqual(row['status'],'ambiguous'); self.assertNotIn('leaf1',row['label'])

    def test_order_independent_digest(self):
        a,b=device(),device('leaf2',address='10.3.1.2/32')
        self.assertEqual(self.build(a,b)['sha256'],self.build(b,a)['sha256'])

    def test_no_prefix_guess(self):
        s=self.build(device(address='10.100.0.10/24'))
        r=enrich_record({'source.address':'10.100.0.99'},s)
        self.assertEqual(r['nautobot.source.status'],'unknown')

    def test_bad_input_fails(self):
        for response in [{},{'errors':['failure']},{'data':{'devices':[]}}]:
            with self.assertRaises(ValueError): build_snapshot(response)
        with self.assertRaises(ValueError): self.build(device(),device())

    def test_processor_scoped_to_flow(self):
        p=processor(self.build(device()))
        self.assertEqual(p['log_statements'][0]['conditions'],['attributes["flow.type"] != nil'])


if __name__=='__main__': unittest.main()
