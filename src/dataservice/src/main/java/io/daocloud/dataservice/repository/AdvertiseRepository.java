package io.daocloud.dataservice.repository;

import io.daocloud.dataservice.entity.Advertise;
import org.springframework.data.repository.CrudRepository;

// This will be AUTO IMPLEMENTED by Spring into a Bean called userRepository
// CRUD refers Create, Read, Update, Delete
public interface AdvertiseRepository extends CrudRepository<Advertise, Integer> {
}
