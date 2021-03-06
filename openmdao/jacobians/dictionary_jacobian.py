"""Define the DictionaryJacobian class."""
from __future__ import division

import numpy as np
from six.moves import range

from openmdao.jacobians.jacobian import Jacobian


class DictionaryJacobian(Jacobian):
    """
    No global <Jacobian>; use dictionary of user-supplied sub-Jacobians.

    Attributes
    ----------
    _iter_keys : list of (vname, vname) tuples
        List of tuples of variable names that match subjacs in the this Jacobian.

    """

    def __init__(self, **kwargs):
        """
        Initialize all attributes.

        Parameters
        ----------
        **kwargs : dict
            options dictionary.
        """
        super(DictionaryJacobian, self).__init__(**kwargs)

        self._iter_keys = {}

    def _iter_abs_keys(self, vec_name):
        """
        Iterate over subjacs keyed by absolute names.

        This includes only subjacs that have been set and are part of the current system.

        Parameters
        ----------
        vec_name : str
            The name of the current RHS vector.

        Returns
        -------
        list
            List of keys matching this jacobian for the current system.
        """
        system = self._system
        entry = (system.pathname, vec_name)

        if entry not in self._iter_keys:
            subjacs = self._subjacs
            keys = []
            for res_name in system._var_relevant_names[vec_name]['output']:
                for type_ in ('output', 'input'):
                    for name in system._var_relevant_names[vec_name][type_]:
                        key = (res_name, name)
                        if key in subjacs:
                            keys.append(key)
            self._iter_keys[entry] = keys
            return keys

        return self._iter_keys[entry]

    def _apply(self, d_inputs, d_outputs, d_residuals, mode):
        """
        Compute matrix-vector product.

        Parameters
        ----------
        d_inputs : Vector
            inputs linear vector.
        d_outputs : Vector
            outputs linear vector.
        d_residuals : Vector
            residuals linear vector.
        mode : str
            'fwd' or 'rev'.
        """
        # avoid circular import
        from openmdao.core.explicitcomponent import ExplicitComponent

        fwd = mode == 'fwd'
        system = self._system
        d_res_names = d_residuals._names
        d_out_names = d_outputs._names
        d_inp_names = d_inputs._names
        res_flat_views = d_residuals._views_flat
        out_flat_views = d_outputs._views_flat
        inp_flat_views = d_inputs._views_flat
        np_add_at = np.add.at

        with system._unscaled_context(outputs=[d_outputs], residuals=[d_residuals]):
            ncol = d_residuals._ncol
            for abs_key in self._iter_abs_keys(d_residuals._name):
                subjac = self._subjacs[abs_key]
                res_name, other_name = abs_key
                if res_name in d_res_names:
                    if isinstance(subjac, list):
                        if other_name in d_out_names:
                            re = res_flat_views[res_name]
                            op = out_flat_views[other_name]
                            # skip the matvec mult completely for identity subjacs
                            if res_name is other_name and isinstance(system, ExplicitComponent):
                                if fwd:
                                    re += op
                                else:
                                    op += re
                            elif fwd:
                                if ncol > 1:
                                    for i in range(ncol):
                                        np_add_at(re[:, i], subjac[1],
                                                  op[:, i][subjac[2]] * subjac[0])
                                else:
                                    np_add_at(re, subjac[1], op[subjac[2]] * subjac[0])
                            else:  # rev
                                if ncol > 1:
                                    for i in range(ncol):
                                        np_add_at(op[:, i], subjac[2],
                                                  re[:, i][subjac[1]] * subjac[0])
                                else:
                                    np_add_at(op, subjac[2], re[subjac[1]] * subjac[0])
                        elif other_name in d_inp_names:
                            re = res_flat_views[res_name]
                            ip = inp_flat_views[other_name]
                            if fwd:
                                if ncol > 1:
                                    for i in range(ncol):
                                        np_add_at(re[:, i], subjac[1],
                                                  ip[:, i][subjac[2]] * subjac[0])
                                else:
                                    np_add_at(re, subjac[1], ip[subjac[2]] * subjac[0])
                            else:  # rev
                                if ncol > 1:
                                    for i in range(ncol):
                                        np_add_at(ip[:, i], subjac[2],
                                                  re[:, i][subjac[1]] * subjac[0])
                                else:
                                    np_add_at(ip, subjac[2], re[subjac[1]] * subjac[0])
                    else:  # ndarray or sparse
                        if other_name in d_out_names:
                            re = res_flat_views[res_name]
                            op = out_flat_views[other_name]
                            if fwd:
                                re += subjac.dot(op)
                            else:  # rev
                                op += subjac.T.dot(re)

                        elif other_name in d_inp_names:
                            re = res_flat_views[res_name]
                            ip = inp_flat_views[other_name]
                            if fwd:
                                re += subjac.dot(ip)
                            else:  # rev
                                ip += subjac.T.dot(re)
