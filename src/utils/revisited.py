import logging
import numpy as np

log = logging.getLogger(__name__)


def compute_rectangular_ap(ranks, nres):
    if len(ranks) < 1:
        return 0.

    mask = np.zeros(ranks.max() + 1)
    mask[ranks] = 1
    prec = np.cumsum(mask) / (np.arange(mask.shape[0]) + 1)
    return (mask * prec).sum() / nres


def compute_trapezoidal_ap(ranks, nres):
    """
    Computes average precision for given ranked indexes.

    Arguments
    ---------
    ranks : zero-based ranks of positive images
    nres  : number of positive images

    Returns
    -------
    ap    : average precision
    """

    # number of images ranked by the system
    nimgranks = len(ranks)

    # accumulate trapezoids in PR-plotㅁ
    ap = 0

    recall_step = 1. / nres

    for j in np.arange(nimgranks):
        rank = ranks[j]

        if rank == 0:
            precision_0 = 1.
        else:
            precision_0 = float(j) / rank

        precision_1 = float(j + 1) / (rank + 1)

        ap += (precision_0 + precision_1) * recall_step / 2.

    return ap


def compute_map(ranks, gnd, kappas=[], ap_f=compute_trapezoidal_ap):
    """
    Computes the mAP for a given set of returned results.

         Usage:
           map = compute_map (ranks, gnd)
                 computes mean average precsion (map) only

           map, aps, pr, prs = compute_map (ranks, gnd, kappas)
                 computes mean average precision (map), average precision (aps) for each query
                 computes mean precision at kappas (pr), precision at kappas (prs) for each query

         Notes:
         1) ranks starts from 0, ranks.shape = db_size X #queries
         2) The junk results (e.g., the query itself) should be declared in the gnd stuct array
         3) If there are no positive images for some query, that query is excluded from the evaluation
    """

    map = 0.
    nq = len(gnd) # number of queries
    aps = np.zeros(nq)
    pr = np.zeros(len(kappas))
    prs = np.zeros((nq, len(kappas)))
    nempty = 0

    for i in np.arange(nq):
        qgnd = np.array(gnd[i]['ok'])

        # no positive images, skip from the average
        if qgnd.shape[0] == 0:
            aps[i] = float('nan')
            prs[i, :] = float('nan')
            nempty += 1
            continue

        try:
            qgndj = np.array(gnd[i]['junk'])
        except:
            qgndj = np.empty(0)

        # sorted positions of positive and junk images (0 based)
        pos  = np.arange(ranks.shape[0])[np.in1d(ranks[:,i], qgnd)]
        junk = np.arange(ranks.shape[0])[np.in1d(ranks[:,i], qgndj)]

        k = 0
        ij = 0
        if len(junk):
            # decrease positions of positives based on the number of
            # junk images appearing before them
            ip = 0
            while (ip < len(pos)):
                while (ij < len(junk) and pos[ip] > junk[ij]):
                    k += 1
                    ij += 1
                pos[ip] = pos[ip] - k
                ip += 1

        # compute ap
        ap = ap_f(pos, min(len(qgnd), ranks.shape[0]))
        map = map + ap
        aps[i] = ap

        # compute precision @ k
        if len(pos) > 0:
            pos += 1 # get it to 1-based
            for j in np.arange(len(kappas)):
                kq = min(max(pos), kappas[j]);
                prs[i, j] = (pos <= kq).sum() / kq
            pr = pr + prs[i, :]

    map = map / (nq - nempty)
    pr = pr / (nq - nempty)

    return map, aps, pr, prs


def compute_metrics(query_dataset, gallery_dataset, ranks, gnd, kappas=[1, 5, 10]):
    dataset_name = query_dataset.name

    if dataset_name == 'gldv2-test':
        ranks = ranks[:100]
        pub_map, pub_aps, _, _ = compute_map(ranks[:, :-750], gnd[:-750], ap_f=compute_rectangular_ap)
        priv_map, priv_aps, _, _ = compute_map(ranks[:, -750:], gnd[-750:], ap_f=compute_rectangular_ap)
        map, aps, _, _ = compute_map(ranks, gnd, ap_f=compute_rectangular_ap)

        out = {'pub_map': np.around(pub_map*100, decimals=3), 'priv_map': np.around(priv_map*100, decimals=3),
               'map': np.around(map*100, decimals=3)}
        info = f'>> {dataset_name}: mAP public: {out["pub_map"]:.3f}, private: {out["priv_map"]:.3f}, combined: {out["map"]:.3f}'

    elif dataset_name == 'gldv2-val':
        ranks = ranks[:100]
        map, aps, _, _ = compute_map(ranks, gnd[:-750], ap_f=compute_rectangular_ap)
        out = {'map': np.around(map*100, decimals=3)}
        info = f'>> {dataset_name}: mAP public: {out["map"]:.3f}'

    elif dataset_name.startswith(('roxford', 'rparis')):

        gnd_t = []
        for i in range(len(gnd)):
            g = {}
            g['ok'] = np.concatenate([gnd[i]['easy']])
            g['junk'] = np.concatenate([gnd[i]['junk'], gnd[i]['hard']])
            gnd_t.append(g)
        mapE, apsE, mprE, prsE = compute_map(ranks, gnd_t, kappas)

        gnd_t = []
        for i in range(len(gnd)):
            g = {}
            g['ok'] = np.concatenate([gnd[i]['easy'], gnd[i]['hard']])
            g['junk'] = np.concatenate([gnd[i]['junk']])
            gnd_t.append(g)
        mapM, apsM, mprM, prsM = compute_map(ranks, gnd_t, kappas)

        gnd_t = []
        for i in range(len(gnd)):
            g = {}
            g['ok'] = np.concatenate([gnd[i]['hard']])
            g['junk'] = np.concatenate([gnd[i]['junk'], gnd[i]['easy']])
            gnd_t.append(g)
        mapH, apsH, mprH, prsH = compute_map(ranks, gnd_t, kappas)


        out = {
            'E_map': np.around(mapE*100, decimals=3),
            'M_map': np.around(mapM*100, decimals=3),
            'H_map': np.around(mapH*100, decimals=3),
            'E_mp':  np.around(mprE*100, decimals=3),
            'M_mp':  np.around(mprM*100, decimals=3),
            'H_mp':  np.around(mprH*100, decimals=3),
            'apsE': apsE.tolist(),
            'apsM': apsM.tolist(),
            'apsH': apsH.tolist(),
        }
        map = (mapM + mapH) / 2
        aps = np.concatenate((apsM, apsH))
        info = f'>> {dataset_name}: mAP M: {out["M_map"]}, H: {out["H_map"]}'
    else:
        info = f'Evaluation protocol for {dataset_name} is not implemented yet!'

    print(info)
    log.info(info)

    return out, map, aps